import asyncio
import os
from pathlib import Path

import httpx

from app.core.database import mongo_db

IMAGE_DIR = Path(os.getenv("IMAGE_DIR", "data/images"))
SEMAPHORE_LIMIT = 5


class ImageDownloader:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self._sem = asyncio.Semaphore(SEMAPHORE_LIMIT)

    async def close(self):
        await self.client.aclose()

    async def download_game_images(self, bgg_id: int, thumbnail_url: str, image_url: str) -> dict:
        game_dir = IMAGE_DIR / str(bgg_id)
        game_dir.mkdir(parents=True, exist_ok=True)

        result = {"local_thumbnail": "", "local_image": ""}

        if thumbnail_url:
            thumb_path = game_dir / "thumb.jpg"
            if not thumb_path.exists():
                data = await self._download(thumbnail_url)
                if data:
                    thumb_path.write_bytes(data)
            result["local_thumbnail"] = str(thumb_path)

        if image_url:
            img_path = game_dir / "original.jpg"
            if not img_path.exists():
                data = await self._download(image_url)
                if data:
                    img_path.write_bytes(data)
            result["local_image"] = str(img_path)

        return result

    async def _download(self, url: str) -> bytes | None:
        async with self._sem:
            try:
                await asyncio.sleep(0.3)
                resp = await self.client.get(url)
                if resp.status_code == 200:
                    return resp.content
            except Exception as e:
                print(f"Image download error {url}: {e}")
        return None

    async def run_batch(self, limit: int = 100):
        games = await mongo_db.board_games.find(
            {"local_thumbnail": "", "thumbnail": {"$ne": ""}},
            {"bgg_id": 1, "thumbnail": 1, "image": 1},
        ).to_list(length=limit)

        print(f"Downloading images for {len(games)} games...")
        tasks = []
        for game in games:
            tasks.append(self.download_game_images(
                game["bgg_id"],
                game.get("thumbnail", ""),
                game.get("image", ""),
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for game, result in zip(games, results):
            if isinstance(result, Exception):
                continue
            await mongo_db.board_games.update_one(
                {"bgg_id": game["bgg_id"]},
                {"$set": result},
            )

        print(f"Image download complete for {len(games)} games")

    async def close(self):
        await self.client.aclose()
