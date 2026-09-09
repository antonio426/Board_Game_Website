"""Make stored Chinese Traditional, and drop the enricher's private copies.

Two problems, one pass:

1. `zhuoyouku_enricher` wrote `description_zh` exactly as the source published
   it, which is Simplified. A zh reader on a Traditional site was reading
   给出一个词的线索 under a 繁體 title. `name_zh` already went through
   `to_traditional`; the description did not.

2. The same enricher mirrored the game into `categories_zh`, `mechanics_zh`,
   `designers_zh`, `publishers_zh`, `genre_zh`, `min_players_zh`,
   `max_players_zh`, `year_published_zhuoyouku` and `name_en_from_zhuoyouku`.
   Nothing reads them: tag names come from `app/core/vocab.py`, which is the
   authority, and the rest duplicate fields BGG already fills. They are dead
   weight in every document and a second, Simplified, contradicting copy of the
   vocabulary.

Both are re-derivable by re-running the enricher, so this rewrites in place.

Usage:
    cd backend && .venv/bin/python scripts/traditionalize_zh.py            # report
    cd backend && .venv/bin/python scripts/traditionalize_zh.py --apply
"""
import argparse
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from pymongo import UpdateOne

from app.core.cjk import to_traditional
from app.core.database import mongo_db

# Written by the enricher, read by nobody.
MIRROR_FIELDS = (
    "categories_zh",
    "mechanics_zh",
    "designers_zh",
    "publishers_zh",
    "genre_zh",
    "min_players_zh",
    "max_players_zh",
    "year_published_zhuoyouku",
    "name_en_from_zhuoyouku",
)

TEXT_FIELDS = ("name_zh", "description_zh")

BATCH = 500


async def convert_text(apply: bool) -> tuple[int, int]:
    """Rewrite any Chinese text field that is not already Traditional."""
    cursor = mongo_db.board_games.find(
        {"$or": [{field: {"$nin": ["", None]}} for field in TEXT_FIELDS]},
        {field: 1 for field in TEXT_FIELDS},
    )

    seen = 0
    operations: list[UpdateOne] = []
    changed = 0
    async for doc in cursor:
        seen += 1
        update = {}
        for field in TEXT_FIELDS:
            value = doc.get(field)
            if not value:
                continue
            traditional = to_traditional(value)
            if traditional != value:
                update[field] = traditional
        if not update:
            continue
        changed += 1
        operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": update}))
        if apply and len(operations) >= BATCH:
            await mongo_db.board_games.bulk_write(operations, ordered=False)
            operations = []

    if apply and operations:
        await mongo_db.board_games.bulk_write(operations, ordered=False)
    return seen, changed


async def drop_mirrors(apply: bool) -> int:
    query = {"$or": [{field: {"$exists": True}} for field in MIRROR_FIELDS]}
    affected = await mongo_db.board_games.count_documents(query)
    if apply and affected:
        await mongo_db.board_games.update_many(
            query, {"$unset": {field: "" for field in MIRROR_FIELDS}}
        )
    return affected


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args()

    seen, changed = await convert_text(args.apply)
    mirrors = await drop_mirrors(args.apply)

    verb = "converted" if args.apply else "would convert"
    print(f"{verb} {changed} of {seen} documents carrying Chinese text")
    verb = "cleared" if args.apply else "would clear"
    print(f"{verb} enricher mirror fields on {mirrors} documents")
    if not args.apply:
        print("\nnothing written; re-run with --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
