"""Fill `name_zh` with the official Chinese title BGG already knows.

Machine translation is the wrong tool for game names: the Chinese title is
whatever the local publisher chose, not a rendering of the English one —
Splendor is 璀璨寶石, Wingspan is 展翅翱翔. BGG carries those under
`alternatenames`, so this reads them rather than inventing them.

Every CJK alternate is kept in `aliases` so search still matches the Japanese
or simplified form, but `name_zh` is only set from a name that passes
`is_chinese`, which is what stopped カタン スタンダード版 being displayed as
Catan's Chinese name.

Games are processed most-rated first and each one records `zh_names_at`, so the
job can be stopped and restarted at will.

Usage:
    cd backend && .venv/bin/python scripts/backfill_zh_names.py --limit 50
    cd backend && .venv/bin/python scripts/backfill_zh_names.py
    cd backend && .venv/bin/python scripts/backfill_zh_names.py --min-users-rated 500
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

from app.core.cjk import has_cjk, is_chinese, to_traditional
from app.core.database import mongo_db, redis_client
from app.core.quality import QUALITY_FILTER

API = "https://api.geekdo.com/api/geekitems"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
# geekdo answers 429 above roughly ten requests a second across all jobs.
CONCURRENCY = 2
REQUEST_DELAY_SECONDS = 0.4
MAX_RETRIES = 3
FLUSH_EVERY = 100


# Edition markers: BGG lists "卡坦 : 基礎" and "拼布對決: 臺灣意象" alongside the
# plain titles 卡坦島 and 拼布藝術, and the plain one is what a person searches.
EDITION_MARKERS = ("：", ":", "版", "限定", "擴充", "扩充", "紀念", "纪念")


def pick_chinese_name(candidates: list[str]) -> str | None:
    """The plainest Chinese title on offer."""
    if not candidates:
        return None
    plain = [name for name in candidates if not any(mark in name for mark in EDITION_MARKERS)]
    return min(plain or candidates, key=len)


def parse(payload: dict) -> dict:
    """Chinese name and every CJK alias the item carries."""
    item = (payload or {}).get("item") or {}
    names = []

    primary = (item.get("primaryname") or {}).get("name")
    if primary:
        names.append(primary)
    for entry in item.get("alternatenames") or []:
        name = entry.get("name") if isinstance(entry, dict) else entry
        if name:
            names.append(name)

    cjk_names = [to_traditional(name) for name in names if has_cjk(name)]
    chinese = [name for name in cjk_names if is_chinese(name)]

    fields: dict = {"zh_names_at": datetime.now(timezone.utc)}
    chosen = pick_chinese_name(chinese)
    if chosen:
        fields["name_zh"] = chosen
    return {"set": fields, "aliases": cjk_names}


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


async def main(limit: int | None, min_users_rated: int, refresh: bool) -> None:
    query = dict(QUALITY_FILTER)
    if min_users_rated:
        query["users_rated"] = {"$gte": min_users_rated}
    if refresh:
        # Re-check games already looked at, e.g. after changing which of the
        # alternate names counts as the title.
        query["zh_names_at"] = {"$exists": True}
    else:
        query["name_zh"] = {"$in": [None, ""]}
        query["zh_names_at"] = {"$exists": False}

    pending = await mongo_db.board_games.count_documents(query)
    cursor = mongo_db.board_games.find(query, {"bgg_id": 1}).sort("users_rated", -1)
    if limit:
        cursor = cursor.limit(limit)
    todo = [doc["bgg_id"] async for doc in cursor]
    print(f"[start] missing zh names={pending:,} processing={len(todo):,}", flush=True)

    semaphore = asyncio.Semaphore(CONCURRENCY)
    writes: list[UpdateOne] = []
    started = time.monotonic()
    done = named = failed = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=20.0,
    ) as client:

        async def worker(bgg_id: int) -> None:
            nonlocal done, named, failed
            async with semaphore:
                result = await fetch(client, bgg_id)
                await asyncio.sleep(REQUEST_DELAY_SECONDS)

            done += 1
            if result is None:
                failed += 1
                return
            if "name_zh" in result["set"]:
                named += 1

            update: dict = {"$set": result["set"]}
            if result["aliases"]:
                update["$addToSet"] = {"aliases": {"$each": result["aliases"]}}
            writes.append(UpdateOne({"bgg_id": bgg_id}, update))

        for start in range(0, len(todo), FLUSH_EVERY):
            await asyncio.gather(*(worker(bgg_id) for bgg_id in todo[start:start + FLUSH_EVERY]))
            if writes:
                await mongo_db.board_games.bulk_write(writes, ordered=False)
                writes = []
            elapsed = time.monotonic() - started
            rate = done / elapsed if elapsed else 0
            print(f"[{done:,}/{len(todo):,}] chinese_names={named:,} failed={failed:,} "
                  f"{rate:.1f}/s eta={(len(todo) - done) / rate / 60 if rate else 0:.0f}min", flush=True)

    total = await mongo_db.board_games.count_documents({"name_zh": {"$nin": [None, ""]}})
    print(f"[done] processed={done:,} chinese_names={named:,} failed={failed:,} "
          f"name_zh now on {total:,} documents", flush=True)

    try:
        redis_client.flushdb()
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-users-rated", type=int, default=0)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.min_users_rated, args.refresh))
