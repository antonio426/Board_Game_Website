"""Mark expansions using the geekdo item API.

`is_expansion` was true on exactly 1 of 180,401 documents, so expansions were
treated as standalone games everywhere: the top of a `quality_score` sort was
almost entirely Spirit Island and Ark Nova expansions, and searching "Catan"
buried the base game under its own add-ons.

`api.geekdo.com/api/geekitems` reports the real subtype regardless of the
subtype passed in the query, so one request per game settles it.

Usage:
    cd backend && .venv/bin/python scripts/backfill_subtypes.py --limit 50
    cd backend && .venv/bin/python scripts/backfill_subtypes.py
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

API = "https://api.geekdo.com/api/geekitems"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
EXPANSION_SUBTYPES = {"boardgameexpansion", "boardgameaccessory"}
CONCURRENCY = 8
REQUEST_DELAY_SECONDS = 0.1
MAX_RETRIES = 3
FLUSH_EVERY = 200


def parse(payload: dict) -> dict | None:
    item = (payload or {}).get("item") or {}
    subtype = item.get("subtype")
    if not subtype:
        return None
    subtypes = [s for s in (item.get("subtypes") or []) if isinstance(s, str)]
    return {
        "subtype": subtype,
        "subtypes": subtypes or [subtype],
        "is_expansion": subtype in EXPANSION_SUBTYPES,
        "subtype_at": datetime.now(timezone.utc),
    }


async def fetch(client: httpx.AsyncClient, bgg_id: int) -> dict | None:
    params = {"objectid": bgg_id, "objecttype": "thing", "subtype": "boardgame"}
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.get(API, params=params)
            if response.status_code == 429:
                await asyncio.sleep(3 * (attempt + 1))
                continue
            if response.status_code != 200:
                return None
            return parse(response.json())
        except Exception:
            await asyncio.sleep(1 + attempt)
    return None


async def main(limit: int | None, refresh: bool) -> None:
    query = dict(QUALITY_FILTER)
    if not refresh:
        query["subtype_at"] = {"$exists": False}

    pending = await mongo_db.board_games.count_documents(query)
    cursor = mongo_db.board_games.find(query, {"bgg_id": 1}).sort("users_rated", -1)
    if limit:
        cursor = cursor.limit(limit)
    todo = [doc["bgg_id"] async for doc in cursor]
    print(f"[start] pending={pending:,} processing={len(todo):,}", flush=True)

    semaphore = asyncio.Semaphore(CONCURRENCY)
    writes: list[UpdateOne] = []
    started = time.monotonic()
    done = expansions = failed = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=20.0,
    ) as client:

        async def worker(bgg_id: int) -> None:
            nonlocal done, expansions, failed
            async with semaphore:
                fields = await fetch(client, bgg_id)
                await asyncio.sleep(REQUEST_DELAY_SECONDS)
            done += 1
            if fields is None:
                failed += 1
                return
            if fields["is_expansion"]:
                expansions += 1
            writes.append(UpdateOne({"bgg_id": bgg_id}, {"$set": fields}))

        for start in range(0, len(todo), FLUSH_EVERY):
            await asyncio.gather(*(worker(bgg_id) for bgg_id in todo[start:start + FLUSH_EVERY]))
            if writes:
                await mongo_db.board_games.bulk_write(writes, ordered=False)
                writes = []
            elapsed = time.monotonic() - started
            rate = done / elapsed if elapsed else 0
            print(f"[{done:,}/{len(todo):,}] expansions={expansions:,} failed={failed:,} "
                  f"{rate:.1f}/s eta={(len(todo) - done) / rate / 60 if rate else 0:.0f}min", flush=True)

    print(f"[done] processed={done:,} expansions={expansions:,} failed={failed:,}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.refresh))
