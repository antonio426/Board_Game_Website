"""Set `is_expansion` from the rank the catalogue already carries.

BGG ranks every base game once it has about 30 ratings and never ranks an
expansion, so a well-rated game with no rank is an expansion. The importer
already stores `bgg_rank = 99999` for unranked items, so this needs no network
calls at all.

Checked against the 3,296 games labelled through the authoritative item API:
all 43 expansions are unranked and all 3,253 base games are ranked, with no
exceptions either way.

An unranked game with fewer than `MIN_VOTES` ratings is genuinely ambiguous —
it may be an expansion, or a base game nobody has rated — so it is left alone
rather than hidden. Documents whose subtype came from
`scripts/backfill_subtypes.py` are also left alone: that flag is authoritative
and this one is only an inference.

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

# BGG's "no rank" sentinel, as stored by the importer.
UNRANKED = 99999
# Below this many ratings, being unranked says nothing either way.
MIN_VOTES = 30

INFERRED = {"subtype_at": {"$exists": False}}


async def main(dry_run: bool) -> None:
    expansions = {**INFERRED, "bgg_rank": {"$gte": UNRANKED}, "users_rated": {"$gte": MIN_VOTES}}
    base_games = {**INFERRED, "bgg_rank": {"$lt": UNRANKED}}

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
