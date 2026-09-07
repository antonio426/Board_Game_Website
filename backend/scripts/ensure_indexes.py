"""Create the `board_games` indexes defined in app/core/indexes.py.

The FastAPI app also runs this on startup; this script exists so indexes can be
built (and timed) without booting the API.

Usage:
    cd backend && .venv/bin/python scripts/ensure_indexes.py
"""
import asyncio
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.core.database import mongo_db
from app.core.indexes import ensure_indexes


async def main() -> None:
    dupes = await mongo_db.board_games.aggregate([
        {"$group": {"_id": "$bgg_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$count": "duplicates"},
    ]).to_list(length=1)
    if dupes:
        print(f"[warn] {dupes[0]['duplicates']} duplicate bgg_id values — unique index will fail")

    started = time.monotonic()
    created = await ensure_indexes()
    elapsed = time.monotonic() - started

    existing = await mongo_db.board_games.index_information()
    print(f"[done] requested={len(created)} elapsed={elapsed:.1f}s")
    for name in sorted(existing):
        print(f"  {name}")


if __name__ == "__main__":
    asyncio.run(main())
