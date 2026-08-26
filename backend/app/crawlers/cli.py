import asyncio
import argparse

from app.crawlers.bgg_crawler import BGGCrawler


def main():
    parser = argparse.ArgumentParser(description="BGG Crawler")
    parser.add_argument("--limit", type=int, default=2000, help="Number of games to crawl")
    parser.add_argument("--ids", type=str, default=None, help="Comma-separated BGG IDs to fetch")
    args = parser.parse_args()

    crawler = BGGCrawler()

    if args.ids:
        ids = [int(x.strip()) for x in args.ids.split(",")]
        print(f"Fetching specific IDs: {ids}")
        async def _run_ids():
            games = await crawler.fetch_game_data(ids)
            await crawler.save_games(games)
            await crawler.close()
        asyncio.run(_run_ids())
    else:
        asyncio.run(crawler.run(limit=args.limit))


if __name__ == "__main__":
    main()
