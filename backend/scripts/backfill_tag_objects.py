"""Repair the `categories` / `mechanics` arrays inside game documents.

Three shapes are in the data:

  1. plain strings — 10,959 documents predate the object migration. Read-time
     normalization cannot save these, because `{"categories.name": "Card Game"}`
     will never match `categories: ["Card Game"]`: tag filtering silently misses
     a quarter of the catalogue until the documents themselves are fixed.
  2. objects whose `name_zh` echoes the English name — written by
     `POST /translate/terms` whenever a term was missing from its dictionary.
  3. objects with a null `name` — the entries that made Splendor's categories
     render as `,,`.

`bgg_categories` and `bgg_mechanics` are the source of truth. Do not reach for
`scripts/translate_and_migrate.py` instead: its `build_mapping_collection` drops
those two collections and rebuilds them from whatever the database currently
contains.

Usage:
    cd backend && .venv/bin/python scripts/backfill_tag_objects.py --dry-run
    cd backend && .venv/bin/python scripts/backfill_tag_objects.py
"""
import argparse
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from pymongo import UpdateOne

from app.core.database import mongo_db, redis_client
from app.core.vocab import TAG_COLLECTIONS, vocabulary

BATCH_SIZE = 2000
PROJECTION = {"categories": 1, "mechanics": 1}


async def _mappings() -> dict[str, dict[str, dict]]:
    """field -> {english name -> {id, name, name_zh}}"""
    return {
        field: {row["name"]: row for row in await vocabulary(field)}
        for field in TAG_COLLECTIONS
    }


def repair(items, mapping: dict[str, dict]) -> tuple[list[dict], bool]:
    """Return the corrected array and whether anything actually changed."""
    repaired: list[dict] = []
    changed = False

    for item in items or []:
        if isinstance(item, str):
            name, tag_id, name_zh = item, None, None
            changed = True
        elif isinstance(item, dict):
            name, tag_id, name_zh = item.get("name"), item.get("id"), item.get("name_zh")
        else:
            changed = True
            continue

        if not name:
            changed = True
            continue

        known = mapping.get(name)
        correct_zh = known["name_zh"] if known else (name_zh or name)
        correct_id = tag_id if tag_id else (known["id"] if known else 0)

        if name_zh != correct_zh or tag_id != correct_id:
            changed = True
        repaired.append({"id": correct_id, "name": name, "name_zh": correct_zh})

    return repaired, changed


async def main(dry_run: bool) -> None:
    mappings = await _mappings()
    for field, mapping in mappings.items():
        print(f"[mapping] {field}: {len(mapping)} terms")

    writes: list[UpdateOne] = []
    scanned = touched = 0
    per_field = {field: 0 for field in TAG_COLLECTIONS}

    async for doc in mongo_db.board_games.find({}, PROJECTION):
        scanned += 1
        update: dict = {}
        for field, mapping in mappings.items():
            if field not in doc:
                continue
            repaired, changed = repair(doc[field], mapping)
            if changed:
                update[field] = repaired
                per_field[field] += 1

        if not update:
            continue
        touched += 1
        writes.append(UpdateOne({"_id": doc["_id"]}, {"$set": update}))

        if len(writes) >= BATCH_SIZE and not dry_run:
            await mongo_db.board_games.bulk_write(writes, ordered=False)
            writes = []

    if writes and not dry_run:
        await mongo_db.board_games.bulk_write(writes, ordered=False)

    print(f"[done] scanned={scanned:,} repaired={touched:,} "
          + " ".join(f"{field}={count:,}" for field, count in per_field.items())
          + (" (dry run)" if dry_run else ""))

    if dry_run:
        return

    for field in TAG_COLLECTIONS:
        left = await mongo_db.board_games.count_documents({field: {"$elemMatch": {"$type": "string"}}})
        print(f"[verify] {field} still string-shaped: {left:,}")

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
