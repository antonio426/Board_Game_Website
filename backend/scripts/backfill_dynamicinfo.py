"""Backfill weight, player polls and subdomain ranks from the geekdo API.

The BGG XML API (`/xmlapi2/thing?stats=1`) now answers 401 without credentials,
but `api.geekdo.com/api/dynamicinfo` is open and returns strictly more of what
this site needs:

    bgg_weight            average complexity 1-5  (was populated on 9 of 180k docs)
    bgg_weight_votes      vote count behind it
    best_players          player counts BGG users voted "best"
    recommended_players   player counts voted "recommended"
    language_dependence   text label, matters for the zh audience
    player_age            suggested age
    subcategory_ranks     per-subdomain rank (Strategy, Family, Party, ...)

One request per game and no batch parameter, so the job is resumable: it walks
the showable set ordered by `users_rated` descending, skips anything already
carrying `dynamicinfo_at`, and can be stopped and restarted at any point.

Usage:
    cd backend && .venv/bin/python scripts/backfill_dynamicinfo.py --limit 50
    cd backend && .venv/bin/python scripts/backfill_dynamicinfo.py
    cd backend && .venv/bin/python scripts/backfill_dynamicinfo.py --min-users-rated 100
"""
import argparse
import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import httpx
from pymongo import UpdateOne

from app.core.database import mongo_db
from app.core.quality import QUALITY_FILTER

API = "https://api.geekdo.com/api/dynamicinfo"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
# The geekdo API starts answering 429 above roughly ten requests a second
# across all jobs, so this stays deliberately modest.
CONCURRENCY = 2
REQUEST_DELAY_SECONDS = 0.4
MAX_RETRIES = 3
FLUSH_EVERY = 200


def _player_counts(entries: list | None) -> list[int]:
    """Flatten BGG's [{min, max}] poll ranges into explicit player counts."""
    counts: set[int] = set()
    for entry in entries or []:
        try:
            low, high = int(entry["min"]), int(entry["max"])
        except (KeyError, TypeError, ValueError):
            continue
        if low > high or high - low > 20:
            continue
        counts.update(range(low, high + 1))
    return sorted(counts)


def _to_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def parse(payload: dict) -> dict:
    item = (payload or {}).get("item") or {}
    polls = item.get("polls") or {}
    weight = (polls.get("boardgameweight") or {})

    fields: dict = {"dynamicinfo_at": datetime.now(timezone.utc)}

    average_weight = _to_float(weight.get("averageweight"))
    if average_weight is not None:
        fields["bgg_weight"] = round(average_weight, 4)
        fields["bgg_weight_votes"] = int(_to_float(weight.get("votes")) or 0)

    user_players = polls.get("userplayers") or {}
    best = _player_counts(user_players.get("best"))
    recommended = _player_counts(user_players.get("recommended"))
    if best:
        fields["best_players"] = best
    if recommended:
        fields["recommended_players"] = sorted(set(recommended) | set(best))

    if polls.get("languagedependence"):
        fields["language_dependence"] = polls["languagedependence"]
    if polls.get("playerage"):
        fields["player_age"] = polls["playerage"]

    ranks = []
    for entry in item.get("rankinfo") or []:
        rank = _to_float(entry.get("rank"))
        if rank is None:
            continue
        ranks.append({
            "name": entry.get("prettyname") or "",
            "subdomain": entry.get("subdomain"),
            "rank": int(rank),
            "bayes_average": _to_float(entry.get("baverage")),
        })
    if ranks:
        fields["subcategory_ranks"] = ranks

    # BGG ranks every base game that has ratings and never ranks expansions, so
    # an item with no ranks at all is almost certainly an expansion. Checked
    # against 3,296 games labelled through the authoritative item API: it caught
    # all 43 expansions with 9 false positives, all obscure unranked base games.
    # `scripts/backfill_subtypes.py` overwrites this with the real subtype.
    fields["is_expansion_guess"] = not ranks

    return fields


async def fetch(client: httpx.AsyncClient, bgg_id: int) -> dict | None:
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.get(API, params={"objectid": bgg_id, "objecttype": "thing"})
            if response.status_code == 429:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            if response.status_code != 200:
                return None
            return parse(response.json())
        except Exception:
            await asyncio.sleep(1 + attempt)
    return None


async def main(limit: int | None, min_users_rated: int, refresh: bool) -> None:
    query = dict(QUALITY_FILTER)
    if min_users_rated:
        query["users_rated"] = {"$gte": min_users_rated}
    if not refresh:
        query["dynamicinfo_at"] = {"$exists": False}

    pending_total = await mongo_db.board_games.count_documents(query)
    cursor = mongo_db.board_games.find(query, {"bgg_id": 1, "subtype_at": 1}).sort("users_rated", -1)
    if limit:
        cursor = cursor.limit(limit)

    todo: list[tuple[int, bool]] = [
        (doc["bgg_id"], "subtype_at" in doc) async for doc in cursor
    ]
    print(f"[start] pending={pending_total:,} processing={len(todo):,}", flush=True)

    semaphore = asyncio.Semaphore(CONCURRENCY)
    writes: list[UpdateOne] = []
    started = time.monotonic()
    done = weighted = failed = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=20.0,
    ) as client:

        async def worker(bgg_id: int, has_authoritative_subtype: bool) -> None:
            nonlocal done, weighted, failed
            async with semaphore:
                fields = await fetch(client, bgg_id)
                await asyncio.sleep(REQUEST_DELAY_SECONDS)

            done += 1
            if fields is None:
                failed += 1
                return
            if "bgg_weight" in fields:
                weighted += 1
            if not has_authoritative_subtype:
                fields["is_expansion"] = fields["is_expansion_guess"]
            writes.append(UpdateOne({"bgg_id": bgg_id}, {"$set": fields}))

        for start in range(0, len(todo), FLUSH_EVERY):
            chunk = todo[start:start + FLUSH_EVERY]
            await asyncio.gather(*(worker(bgg_id, labelled) for bgg_id, labelled in chunk))

            if writes:
                await mongo_db.board_games.bulk_write(writes, ordered=False)
                writes = []

            elapsed = time.monotonic() - started
            rate = done / elapsed if elapsed else 0
            remaining = (len(todo) - done) / rate if rate else 0
            print(
                f"[{done:,}/{len(todo):,}] weight={weighted:,} failed={failed:,} "
                f"{rate:.1f}/s eta={remaining / 60:.0f}min",
                flush=True,
            )

    print(f"[done] processed={done:,} with_weight={weighted:,} failed={failed:,}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="stop after N games")
    parser.add_argument("--min-users-rated", type=int, default=0)
    parser.add_argument("--refresh", action="store_true", help="re-fetch games already done")
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.min_users_rated, args.refresh))
