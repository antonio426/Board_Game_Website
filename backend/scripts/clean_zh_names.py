"""Stop showing Japanese titles as if they were Chinese.

641 of the 3,280 populated `name_zh` values are Japanese — Catan is stored as
カタン スタンダード版, Ticket to Ride as 乗車券 — because the enrichers accepted
any CJK alternate name BGG offered. The zh interface then displayed them as the
Chinese title.

Each Japanese title moves into `aliases`, so searching for it still works, and
`name_zh` is either promoted from a kana-free alias or cleared, in which case
the UI falls back to the English name.

Usage:
    cd backend && .venv/bin/python scripts/clean_zh_names.py --dry-run
    cd backend && .venv/bin/python scripts/clean_zh_names.py
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from pymongo import UpdateOne

from app.core.database import mongo_db, redis_client

KANA = re.compile(r"[぀-ゟ゠-ヿ]")
HAN = re.compile(r"[一-鿿]")
BATCH_SIZE = 500


def is_japanese(text: str) -> bool:
    return bool(KANA.search(text or ""))


def is_chinese(text: str) -> bool:
    return bool(HAN.search(text or "")) and not is_japanese(text)


async def main(dry_run: bool) -> None:
    writes: list[UpdateOne] = []
    scanned = promoted = cleared = 0

    cursor = mongo_db.board_games.find(
        {"name_zh": {"$nin": [None, ""]}},
        {"bgg_id": 1, "name_zh": 1, "aliases": 1},
    )

    async for doc in cursor:
        japanese_name = doc["name_zh"]
        if not is_japanese(japanese_name):
            continue
        scanned += 1

        aliases = [alias for alias in doc.get("aliases") or [] if isinstance(alias, str)]
        if japanese_name not in aliases:
            aliases.append(japanese_name)

        replacement = next((alias for alias in aliases if is_chinese(alias)), "")
        if replacement:
            promoted += 1
        else:
            cleared += 1

        writes.append(UpdateOne(
            {"_id": doc["_id"]},
            {"$set": {"name_zh": replacement, "aliases": aliases}},
        ))

        if len(writes) >= BATCH_SIZE and not dry_run:
            await mongo_db.board_games.bulk_write(writes, ordered=False)
            writes = []

    if writes and not dry_run:
        await mongo_db.board_games.bulk_write(writes, ordered=False)

    print(f"[done] japanese titles={scanned:,} promoted from alias={promoted:,} "
          f"cleared={cleared:,}{' (dry run)' if dry_run else ''}")

    if not dry_run:
        remaining = await mongo_db.board_games.count_documents({"name_zh": {"$nin": [None, ""]}})
        print(f"[after] name_zh populated on {remaining:,} documents")
        try:
            redis_client.flushdb()
            print("[cache] Redis flushed")
        except Exception as exc:
            print(f"[cache] flush failed: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
