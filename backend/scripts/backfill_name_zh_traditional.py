"""One-shot backfill: ensure all board_games.name_zh are Traditional Chinese.

Project policy: board game Chinese names must be Traditional Chinese (繁體).
Existing data may contain Simplified Chinese (简体) from zhuoyouku/geekdo/
wikidata enrichers that ran before the cjk fix was deployed. This script
walks the entire `board_games` collection, runs `to_traditional()` on every
non-empty `name_zh`, and bulk-writes the converted values back.

Idempotent: `to_traditional()` is a no-op on already-Traditional and on
non-CJK text, so re-running is safe. Skips writes where the converted value
equals the original (already-Traditional or English-only names).

Usage:
    cd backend && .venv/bin/python scripts/backfill_name_zh_traditional.py --dry-run
    cd backend && .venv/bin/python scripts/backfill_name_zh_traditional.py

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
    with_zh = await mongo_db.board_games.count_documents(
        {"name_zh": {"$exists": True, "$ne": ""}}
    )
    with_cjk = await mongo_db.board_games.count_documents(
        {"name_zh": {"$regex": "[\\x{3400}-\\x{9fff}\\x{f900}-\\x{faff}]"}}
    )
    print(f"[counts] total={total} has_name_zh={with_zh} has_cjk_name_zh={with_cjk}")

    if dry_run:
        print("[dry-run] no writes performed.")
        return

    if with_cjk == 0:
        print("[done] no CJK name_zh documents; nothing to convert.")
        return

    cursor = mongo_db.board_games.find(
        {"name_zh": {"$exists": True, "$ne": ""}},
        projection={"_id": 1, "name_zh": 1},
    )

    pending: list[UpdateOne] = []
    scanned = 0
    converted = 0
    skipped = 0
    batches_flushed = 0

    async for doc in cursor:
        scanned += 1
        original = doc.get("name_zh", "")
        if not original or not has_cjk(original):
            skipped += 1
            continue
        new_value = to_traditional(original)
        if new_value == original:
            skipped += 1
            continue
        pending.append(
            UpdateOne({"_id": doc["_id"]}, {"$set": {"name_zh": new_value}})
        )
        converted += 1
        if len(pending) >= batch_size:
            await mongo_db.board_games.bulk_write(pending, ordered=False)
            batches_flushed += 1
            pending.clear()
            if batches_flushed % 10 == 0:
                print(f"  ... scanned={scanned} converted={converted} batches={batches_flushed}")

    if pending:
        await mongo_db.board_games.bulk_write(pending, ordered=False)
        batches_flushed += 1

    print(f"[done] scanned={scanned} converted={converted} skipped={skipped} batches={batches_flushed}")

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
