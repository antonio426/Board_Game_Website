"""Build Qdrant vectors for every showable game.

The collection previously held 7,833 points produced by a hash function; those
are not comparable with real embeddings, so `--recreate` drops the collection
first. Re-run this whenever the embedding model or the indexed text changes.

Usage:
    cd backend && .venv/bin/python scripts/index_embeddings.py --recreate
    cd backend && .venv/bin/python scripts/index_embeddings.py --limit 500
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.core.database import qdrant_client
from app.recommenders.embedding import COLLECTION, MODEL_NAME, index_games


async def main(recreate: bool, limit: int | None) -> None:
    if recreate:
        names = [c.name for c in qdrant_client.get_collections().collections]
        if COLLECTION in names:
            qdrant_client.delete_collection(COLLECTION)
            print(f"[reset] dropped collection {COLLECTION}")

    print(f"[start] model={MODEL_NAME}", flush=True)
    started = time.monotonic()
    indexed = await index_games(limit=limit)
    elapsed = time.monotonic() - started

    info = qdrant_client.get_collection(COLLECTION)
    print(f"[done] indexed={indexed:,} in {elapsed / 60:.1f} min points={info.points_count:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.recreate, args.limit))
