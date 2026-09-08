#!/usr/bin/env python3
"""LLM translation of `description_en` into `description_zh`.

The `--terms` mode that used to live here is gone: it carried a duplicate of the
dictionary in `app/api/v1/translate.py` and shared its bug, writing the English
name into `name_zh` for any term the dictionary was missing. Tag translation now
comes from `bgg_categories` / `bgg_mechanics` via
`scripts/backfill_tag_objects.py`.

Usage:
  python scripts/preload_translations.py --descriptions --api-key sk-xxx
  python scripts/preload_translations.py --descriptions --api-key sk-xxx --model gpt-4o-mini
  python scripts/preload_translations.py --descriptions --api-key sk-xxx --batch-size 50 --limit 500
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Ensure backend/ is on sys.path so app.* imports work
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.core.database import mongo_db

try:
    import httpx
except ImportError:
    print("httpx is required: pip install httpx")
    sys.exit(1)

DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
LLM_CONCURRENCY = 5
LLM_RATE_LIMIT = 0.5  # seconds between LLM calls

SYSTEM_PROMPT = """你是一位專業的桌遊翻譯員。請將以下桌遊描述從英文翻譯為繁體中文（台灣用語）。

翻譯規則：
1. 保留所有 HTML 標籤不變（如 <b>, </b>, <br/> 等）
2. 專有名詞（遊戲名稱、人名）保留英文原文
3. 桌遊相關術語請使用台灣桌遊圈常用譯法
4. 輸出純翻譯結果，不要加任何前言或解釋"""


async def translate_one(
    client: httpx.AsyncClient,
    api_base: str,
    api_key: str,
    model: str,
    description_en: str,
    name_en: str,
    sem: asyncio.Semaphore,
) -> str | None:
    """Call OpenAI-compatible chat API to translate one description."""
    async with sem:
        try:
            await asyncio.sleep(LLM_RATE_LIMIT)
            resp = await client.post(
                f"{api_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"【{name_en}】\n\n{description_en}"},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2048,
                },
                timeout=60.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                print(f"    API error {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"    Exception: {e}")
            return None


async def preload_descriptions(
    api_base: str,
    api_key: str,
    model: str,
    batch_size: int = 100,
    limit: int | None = None,
    all_games: bool = False,
) -> dict:
    """Translate description_en → description_zh via LLM for games missing Chinese description."""
    query = {
        "description_en": {"$ne": "", "$exists": True},
        "$or": [
            {"description_zh": ""},
            {"description_zh": {"$exists": False}},
        ],
    }
    projection = {"bgg_id": 1, "name_en": 1, "description_en": 1}

    cursor = mongo_db.board_games.find(query, projection)
    if not all_games and limit:
        cursor = cursor.limit(limit)

    games = await cursor.to_list(length=limit or 0)
    total = len(games)
    print(f"Games needing description translation: {total}")

    if total == 0:
        return {"total": 0, "updated": 0, "failed": 0}

    # Count how many still need translation (for progress reporting)
    pending_count = await mongo_db.board_games.count_documents(query)
    print(f"Total pending in DB: {pending_count}")

    sem = asyncio.Semaphore(LLM_CONCURRENCY)
    updated = 0
    failed = 0

    async with httpx.AsyncClient() as client:
        for i, game in enumerate(games, 1):
            bgg_id = game["bgg_id"]
            name_en = game.get("name_en", f"Game {bgg_id}")
            desc_en = game.get("description_en", "")

            if not desc_en.strip():
                failed += 1
                continue

            desc_zh = await translate_one(client, api_base, api_key, model, desc_en, name_en, sem)

            if desc_zh:
                await mongo_db.board_games.update_one(
                    {"bgg_id": bgg_id},
                    {"$set": {"description_zh": desc_zh}},
                )
                updated += 1
            else:
                failed += 1

            if i % 20 == 0 or i == total:
                print(f"  [{i}/{total}] updated={updated} failed={failed}")

    return {"total": total, "updated": updated, "failed": failed}


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

async def run(args):
    do_descs = args.descriptions or bool(args.api_key)

    if do_descs:
        if not args.api_key:
            print("\nERROR: --descriptions requires --api-key (or TRANSLATION_API_KEY env var)")
            sys.exit(1)

        api_base = args.api_base.rstrip("/")
        print("\n" + "=" * 60)
        print(f"  DESCRIPTION TRANSLATION (LLM)")
        print(f"  API base: {api_base}")
        print(f"  Model:    {args.model}")
        print("=" * 60)
        result = await preload_descriptions(
            api_base=api_base,
            api_key=args.api_key,
            model=args.model,
            batch_size=args.batch_size,
            limit=args.limit,
            all_games=args.all_games,
        )
        print(f"\nDescriptions result: {result}")


def main():
    parser = argparse.ArgumentParser(
        description="Preload Chinese translations into MongoDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--descriptions", action="store_true", help="Translate description_en → description_zh (LLM API)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of games to process (default: 500)")
    parser.add_argument("--all", dest="all_games", action="store_true", help="Process ALL games (no limit)")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for description translation (default: 100)")

    # LLM API options
    parser.add_argument("--api-key", type=str, default=os.getenv("TRANSLATION_API_KEY", ""), help="OpenAI-compatible API key (or set TRANSLATION_API_KEY env var)")
    parser.add_argument("--api-base", type=str, default=os.getenv("TRANSLATION_API_BASE", DEFAULT_API_BASE), help=f"API base URL (default: {DEFAULT_API_BASE})")
    parser.add_argument("--model", type=str, default=os.getenv("TRANSLATION_MODEL", DEFAULT_MODEL), help=f"Model name (default: {DEFAULT_MODEL})")

    args = parser.parse_args()

    if not args.all_games and args.limit is None:
        args.limit = 500  # safe default

    print(f"Preload translations config: descriptions={args.descriptions} limit={args.limit} all={args.all_games}")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
