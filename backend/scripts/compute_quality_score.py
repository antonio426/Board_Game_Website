"""Write a Bayesian `quality_score` onto every game.

Neither existing rating field sorts well on its own:

    bgg_rating      Bayesian, but only on the 43k ranked games
    bgg_avg_rating  raw mean over 140k games, so 1 vote of 10.0 outranks
                    60,000 votes averaging 8.5
    bgg_rank        present on all 180k docs, meaningless past ~25k

The standard fix is to pull the raw average toward the global mean in
proportion to how few votes back it:

    quality_score = (v / (v + m)) * R + (m / (v + m)) * C

    v = users_rated, R = bgg_avg_rating, C = global mean, m = prior weight

A game with no votes therefore scores exactly C and settles mid-list, rather
than topping the page on the strength of a single rating.

m is 1000, not the textbook 100: with a weak prior, a cult game with 2,500
votes at 9.0 outranked Brass: Birmingham with 60,000 votes at 8.6, which is not
what someone browsing "best games" expects to see first.

Usage:
    cd backend && .venv/bin/python scripts/compute_quality_score.py --dry-run
    cd backend && .venv/bin/python scripts/compute_quality_score.py
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from pymongo import UpdateOne

from app.core.database import mongo_db, redis_client

PRIOR_VOTES = 1000
MIN_VOTES_FOR_PRIOR = 100
BATCH_SIZE = 2000


async def global_mean() -> float:
    """Mean rating across games with enough votes to be meaningful."""
    pipeline = [
        {"$match": {"bgg_avg_rating": {"$gt": 0}, "users_rated": {"$gte": MIN_VOTES_FOR_PRIOR}}},
        {"$group": {"_id": None, "mean": {"$avg": "$bgg_avg_rating"}, "count": {"$sum": 1}}},
    ]
    result = await mongo_db.board_games.aggregate(pipeline).to_list(length=1)
    if not result:
        return 6.5
    print(f"[prior] C={result[0]['mean']:.4f} over {result[0]['count']:,} games with >= {MIN_VOTES_FOR_PRIOR} votes (m={PRIOR_VOTES})")
    return result[0]["mean"]


def score(rating: float, votes: int, prior_mean: float) -> float:
    if rating <= 0:
        return round(prior_mean, 4)
    weight = votes / (votes + PRIOR_VOTES)
    return round(weight * rating + (1 - weight) * prior_mean, 4)


async def main(dry_run: bool) -> None:
    prior_mean = await global_mean()

    cursor = mongo_db.board_games.find({}, {"bgg_id": 1, "bgg_avg_rating": 1, "users_rated": 1})
    writes: list[UpdateOne] = []
    scanned = updated = 0
    started = time.monotonic()

    async for doc in cursor:
        scanned += 1
        value = score(doc.get("bgg_avg_rating") or 0, doc.get("users_rated") or 0, prior_mean)
        writes.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"quality_score": value}}))

        if len(writes) >= BATCH_SIZE:
            if not dry_run:
                await mongo_db.board_games.bulk_write(writes, ordered=False)
            updated += len(writes)
            writes = []

    if writes:
        if not dry_run:
            await mongo_db.board_games.bulk_write(writes, ordered=False)
        updated += len(writes)

    print(f"[done] scanned={scanned:,} updated={updated:,} in {time.monotonic() - started:.1f}s"
          f"{' (dry run)' if dry_run else ''}")

    if not dry_run:
        top = await mongo_db.board_games.find(
            {"quality_score": {"$gt": 0}},
            {"name_en": 1, "quality_score": 1, "users_rated": 1, "bgg_avg_rating": 1, "_id": 0},
        ).sort("quality_score", -1).limit(10).to_list(length=10)
        print("\ntop 10 by quality_score:")
        for game in top:
            print(f"  {game['quality_score']:.3f}  {game.get('name_en', '')[:44]:<44}"
                  f" avg={game.get('bgg_avg_rating', 0):.2f} votes={game.get('users_rated', 0):,}")

        try:
            redis_client.flushdb()
            print("\n[cache] Redis flushed")
        except Exception as exc:
            print(f"\n[cache] flush failed (TTL will expire): {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
