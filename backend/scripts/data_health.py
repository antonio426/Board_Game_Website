"""Print field coverage for `board_games`.

Run after every crawler or enricher pass. Coverage silently degrading is how
filters end up querying fields that are 99.99% empty (see bgg_weight).

Usage:
    cd backend && .venv/bin/python scripts/data_health.py
"""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.core.database import mongo_db
from app.core.quality import QUALITY_FILTER, quality_gate

# label -> Mongo filter
CHECKS: dict[str, dict] = {
    "total": {},
    "showable (description_en)": QUALITY_FILTER,
    "showable in zh locale": quality_gate("zh"),
    "name_zh non-empty": {"name_zh": {"$nin": [None, ""]}},
    "description_zh non-empty": {"description_zh": {"$nin": [None, ""]}},
    "aliases present": {"aliases.0": {"$exists": True}},
    "bgg_rating > 0": {"bgg_rating": {"$gt": 0}},
    "bgg_avg_rating > 0": {"bgg_avg_rating": {"$gt": 0}},
    "bgg_weight > 0": {"bgg_weight": {"$gt": 0}},
    "quality_score present": {"quality_score": {"$gt": 0}},
    "users_rated >= 50": {"users_rated": {"$gte": 50}},
    "users_rated >= 1000": {"users_rated": {"$gte": 1000}},
    "designers present": {"designers.0": {"$exists": True}},
    "is_expansion true": {"is_expansion": True},
    "local_image set": {"local_image": {"$nin": [None, ""]}},
}

# Coverage below this share of the showable set is worth flagging.
WARN_BELOW_SHARE = 0.5
WARN_LABELS = ("bgg_weight > 0", "quality_score present")


async def main() -> None:
    results: dict[str, int] = {}
    for label, query in CHECKS.items():
        results[label] = await mongo_db.board_games.count_documents(query)

    showable = results["showable (description_en)"] or 1
    width = max(len(label) for label in results)

    print(f"{'field':<{width}}  {'count':>9}  share of showable")
    print("-" * (width + 30))
    for label, count in results.items():
        print(f"{label:<{width}}  {count:>9,}  {count / showable:>6.1%}")

    print()
    for label in WARN_LABELS:
        if results.get(label, 0) < showable * WARN_BELOW_SHARE:
            print(f"[warn] {label}: {results[label]:,} — filters relying on this return almost nothing")

    indexes = await mongo_db.board_games.index_information()
    print(f"\nindexes: {len(indexes)} ({', '.join(sorted(indexes))})")


if __name__ == "__main__":
    asyncio.run(main())
