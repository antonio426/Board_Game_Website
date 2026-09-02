"""One-shot backfill: populate `aliases` field for existing docs.

After this script:
- Docs that have name_zh but no aliases[] get aliases = [name_zh].
- Docs with existing aliases are NOT touched (avoids clobbering enricher
  output that already has multi-element aliases).
- After this runs, the search side (which already includes aliases regex
  in $or for games.py / recommendations.py / chat.py) will match queries
  against both name_zh and aliases[].

For Splendor specifically, this script will set aliases=['寶石の煌き']
(whatever name_zh currently is). To make Splendor findable by 璀璨寶石,
the geekdo enricher must be re-run with the updated code (which now stores
ALL CJK alternates from BGG), so the Chinese alternate name ends up in
aliases[]. This script alone cannot reach BGG to refresh alternates.

Usage:
    cd backend && .venv/bin/python scripts/backfill_aliases.py --dry-run
    cd backend && .venv/bin/python scripts/backfill_aliases.py

Options:
    --dry-run         Only report counts, do not write to MongoDB.
    --batch-size N    Bulk write batch size (default 500).
"""
import argparse
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from pymongo import UpdateOne

from app.core.database import mongo_db, redis_client
from app.core.cjk import has_cjk, to_traditional


async def main(dry_run: bool, batch_size: int) -> None:
    total = await mongo_db.board_games.count_documents({})
    has_name_zh = await mongo_db.board_games.count_documents(
        {"name_zh": {"$exists": True, "$ne": ""}}
    )
    has_cjk_name_zh = await mongo_db.board_games.count_documents(
        {"name_zh": {"$regex": "[\\x{3400}-\\x{9fff}\\x{f900}-\\x{faff}]"}}
    )
    missing_aliases = await mongo_db.board_games.count_documents(
        {
            "name_zh": {"$exists": True, "$ne": ""},
            "$or": [
                {"aliases": {"$exists": False}},
                {"aliases": None},
                {"aliases": {"$size": 0}},
            ],
        }
    )
    print(
        f"[counts] total={total} has_name_zh={has_name_zh} "
        f"has_cjk_name_zh={has_cjk_name_zh} missing_or_empty_aliases={missing_aliases}"
    )

    if dry_run:
        print("[dry-run] no writes performed.")
        return

    if missing_aliases == 0:
        print("[done] no docs missing aliases; nothing to do.")
        return

    cursor = mongo_db.board_games.find(
        {
            "name_zh": {"$exists": True, "$ne": ""},
            "$or": [
                {"aliases": {"$exists": False}},
                {"aliases": None},
                {"aliases": {"$size": 0}},
            ],
        },
        projection={"_id": 1, "name_zh": 1},
    )

    pending: list[UpdateOne] = []
    scanned = 0
    updated = 0
    skipped = 0
    batches_flushed = 0

    async for doc in cursor:
        scanned += 1
        name_zh = doc.get("name_zh", "")
        if not name_zh:
            skipped += 1
            continue
        aliases_value = [to_traditional(name_zh)] if has_cjk(name_zh) else [name_zh]
        pending.append(
            UpdateOne({"_id": doc["_id"]}, {"$set": {"aliases": aliases_value}})
        )
        updated += 1
        if len(pending) >= batch_size:
            await mongo_db.board_games.bulk_write(pending, ordered=False)
            batches_flushed += 1
            pending.clear()
            if batches_flushed % 10 == 0:
                print(f"  ... scanned={scanned} updated={updated} batches={batches_flushed}")

    if pending:
        await mongo_db.board_games.bulk_write(pending, ordered=False)
        batches_flushed += 1

    print(f"[done] scanned={scanned} updated={updated} skipped={skipped} batches={batches_flushed}")

    try:
        redis_client.flushdb()
        print("[cache] Redis flushdb ok (cached game details invalidated).")
    except Exception as e:
        print(f"[cache] Redis flushdb failed (non-fatal, TTL will expire): {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, batch_size=args.batch_size))
