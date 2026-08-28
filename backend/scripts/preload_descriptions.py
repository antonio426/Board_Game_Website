#!/usr/bin/env python3
"""Batch-enrich missing description_en (and other fields) via Geekdo API.

Reuses app.crawlers.geekdo_enricher.enrich_from_geekdo() which already handles:
  - Fetching from https://api.geekdo.com/api/geekitems
  - Rate limiting (1.5s/request, concurrency 5)
  - Parsing description, categories, mechanics, designers, publishers, name_zh
  - Saving to MongoDB

Usage:
  python scripts/preload_descriptions.py [--batch-size 500] [--max-rank 2000]
  python scripts/preload_descriptions.py --all        # process ALL missing (148k+)
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure backend/ is on sys.path so app.* imports work
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.crawlers.geekdo_enricher import enrich_from_geekdo


async def run(batch_size: int = 500, max_rank: int | None = None, process_all: bool = False):
    """Run enrichment in batches. Each batch fetches `batch_size` games from Geekdo."""
    total_updated = 0
    total_failed = 0
    total_skipped = 0
    round_num = 0

    while True:
        round_num += 1
        effective_max_rank = max_rank if not process_all else None

        print(f"\n{'='*60}")
        print(f"  Round {round_num}  (batch_size={batch_size}, max_rank={effective_max_rank})")
        print(f"{'='*60}")

        stats = await enrich_from_geekdo(
            limit=batch_size,
            only_missing=True,
            max_rank=effective_max_rank,
        )

        total_updated += stats.get("updated", 0)
        total_failed += stats.get("failed", 0)
        total_skipped += stats.get("skipped", 0)

        print(f"\n  Round {round_num} result: {stats}")
        print(f"  Cumulative: updated={total_updated} failed={total_failed} skipped={total_skipped}")

        # If nothing was updated or all failed, we're done
        if stats.get("updated", 0) == 0 and stats.get("skipped", 0) == 0:
            print("\n  No more games to enrich. Done!")
            break

        # If too many failures in a row, stop to avoid burning API quota
        if stats.get("failed", 0) > stats.get("updated", 0) * 3 and stats.get("updated", 0) < 10:
            print("\n  Too many failures — stopping to preserve API quota.")
            break

        # If max_rank is set and we're processing by rank, advance rank window
        if max_rank is not None and not process_all:
            break  # Single batch for ranked mode

    print(f"\n{'='*60}")
    print(f"  FINAL: updated={total_updated} failed={total_failed} skipped={total_skipped}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Preload missing description_en from Geekdo API")
    parser.add_argument("--batch-size", type=int, default=500, help="Games per batch (default: 500)")
    parser.add_argument("--max-rank", type=int, default=None, help="Only enrich games with bgg_rank <= this value")
    parser.add_argument("--all", dest="process_all", action="store_true", help="Process ALL missing games (148k+)")
    args = parser.parse_args()

    if args.process_all:
        print("WARNING: --all will process ~148k games. This will take hours.")
        print("         Press Ctrl+C to abort. Starting in 3s...")
        import time; time.sleep(3)

    asyncio.run(run(
        batch_size=args.batch_size,
        max_rank=args.max_rank,
        process_all=args.process_all,
    ))


if __name__ == "__main__":
    main()
