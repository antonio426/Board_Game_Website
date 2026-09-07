"""Set `is_expansion` from rank data already fetched.

`scripts/backfill_dynamicinfo.py` records `subcategory_ranks`, and BGG never
ranks an expansion, so games that came back with no ranks at all are expansions.
Measured against the games labelled by the authoritative item API: all 43
expansions caught, 9 false positives out of 3,296.

Documents whose subtype came from `scripts/backfill_subtypes.py` are left alone
— that flag is authoritative and this one is an inference.

Usage:
    cd backend && .venv/bin/python scripts/mark_expansions.py --dry-run
    cd backend && .venv/bin/python scripts/mark_expansions.py
"""
import argparse
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.core.database import mongo_db, redis_client

INFERRED = {"dynamicinfo_at": {"$exists": True}, "subtype_at": {"$exists": False}}
# Legacy rows carry `subcategory_ranks` as an empty object rather than an array,
# so "no ranks" has to cover missing, empty array and wrong type alike.
NO_RANKS = {"$expr": {"$eq": [
    {"$size": {"$cond": [{"$isArray": "$subcategory_ranks"}, "$subcategory_ranks", []]}},
    0,
]}}


async def main(dry_run: bool) -> None:
    expansions = {**INFERRED, **NO_RANKS}
    base_games = {**INFERRED, "subcategory_ranks.0": {"$exists": True}}

    expansion_count = await mongo_db.board_games.count_documents(expansions)
    base_count = await mongo_db.board_games.count_documents(base_games)
    print(f"[plan] mark {expansion_count:,} as expansions, {base_count:,} as base games")

    if dry_run:
        return

    await mongo_db.board_games.update_many(expansions, {"$set": {"is_expansion": True}})
    await mongo_db.board_games.update_many(base_games, {"$set": {"is_expansion": False}})

    total = await mongo_db.board_games.count_documents({"is_expansion": True})
    print(f"[done] is_expansion true on {total:,} documents")

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
