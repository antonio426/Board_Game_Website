"""Re-fetch board game metadata via Geekdo API for games missing image URLs.

The Geekdo API (api.geekdo.com/api/geekitems) is the unauthenticated
successor to BGG XMLAPI2 and returns the same metadata (image, thumbnail,
description, categories, mechanics, etc). It does NOT require session
cookies unlike BGG XMLAPI2 which returns 401 for unauthenticated calls.

This script targets the 148k games with no `image` URL in MongoDB and
refreshes their metadata from Geekdo. After this runs, the games will
have `image`/`thumbnail` URLs and you can then run `preload_images.py
--both --all` to download them locally.

Uses `_parse_game_payload` from geekdo_enricher (rate limit 1.5s per
request, default concurrency=5).

Usage:
    cd backend && .venv/bin/python scripts/refetch_geekdo_missing.py --limit 200   # test
    cd backend && .venv/bin/python scripts/refetch_geekdo_missing.py --all          # all 148k

Options:
    --limit N    Process only N games (default 200, used unless --all)
    --all        Process ALL games needing re-fetch
    --concurrency N   Max parallel Geekdo requests (default 5)
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import httpx

from app.crawlers.geekdo_enricher import (
    GEEKDO_BASE,
    REQUEST_TIMEOUT,
    _parse_game_payload,
)
from app.core.database import mongo_db, redis_client


async def ids_needing_refresh() -> list[int]:
    cursor = mongo_db.board_games.find(
        {
            "bgg_id": {"$exists": True, "$ne": None},
            "$or": [
                {"thumbnail": {"$exists": False}},
                {"thumbnail": ""},
                {"image": {"$exists": False}},
                {"image": ""},
            ],
        },
        projection={"bgg_id": 1},
    )
    out: list[int] = []
    async for doc in cursor:
        bid = doc.get("bgg_id")
        if bid:
            out.append(int(bid))
    return out


async def refresh_one(client: httpx.AsyncClient, sem: asyncio.Semaphore, bgg_id: int) -> tuple[int, dict | None]:
    url = f"{GEEKDO_BASE}?objectid={bgg_id}&objecttype=thing&showstats=1"
    async with sem:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return bgg_id, None
            payload = resp.json()
            update = _parse_game_payload(payload, bgg_id)
            update.pop("bgg_id", None)
            return bgg_id, (update if update else None)
        except Exception:
            return bgg_id, None


async def main(limit: int | None, concurrency: int) -> None:
    print("[refetch] finding games needing Geekdo re-fetch...")
    ids = await ids_needing_refresh()
    total_available = len(ids)
    print(f"[refetch] {total_available} games need re-fetch")

    if limit is not None:
        ids = ids[:limit]
        print(f"[refetch] limiting to {len(ids)} games")

    if not ids:
        print("[refetch] nothing to do")
        return

    started = time.monotonic()
    saved = 0
    failed = 0
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "BoardGameHub/1.0 (geekdo-enricher)"},
    ) as client:
        batch_size = 50
        for i in range(0, len(ids), batch_size):
            batch = ids[i : i + batch_size]
            tasks = [refresh_one(client, sem, bid) for bid in batch]
            for bid, update in await asyncio.gather(*tasks):
                if update:
                    await mongo_db.board_games.update_one(
                        {"bgg_id": bid}, {"$set": update}
                    )
                    saved += 1
                else:
                    failed += 1

            done = min(i + batch_size, len(ids))
            elapsed = time.monotonic() - started
            rate = done / elapsed if elapsed > 0 else 0
            remaining = (len(ids) - done) / rate if rate > 0 else 0
            if (i // batch_size) % 4 == 0 or done == len(ids):
                print(
                    f"[refetch] {done}/{len(ids)}  "
                    f"saved={saved} failed={failed}  "
                    f"elapsed={elapsed:.0f}s rate={rate:.1f}/s eta={remaining:.0f}s"
                )

    elapsed = time.monotonic() - started
    print(
        f"[refetch] complete: saved={saved}/{len(ids)} "
        f"failed={failed} elapsed={elapsed:.0f}s"
    )

    try:
        redis_client.flushdb()
        print("[cache] Redis flushdb ok")
    except Exception as e:
        print(f"[cache] Redis flushdb failed (non-fatal): {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--all", dest="all_games", action="store_true")
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()

    limit = None if args.all_games else (args.limit if args.limit is not None else 200)
    asyncio.run(main(limit, args.concurrency))
