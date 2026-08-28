#!/usr/bin/env python3
"""Batch-translate Chinese fields in MongoDB: category/mechanic terms + descriptions.

Two modes:
  1. --terms          Deterministic translation using TERM_DICT (no API needed).
                     Translates categories.name_zh and mechanics.name_zh.
  2. --descriptions   LLM-based translation of description_en → description_zh.
                     Requires an OpenAI-compatible API endpoint + key.

Usage:
  # Terms (deterministic, no API key needed):
  python scripts/preload_translations.py --terms
  python scripts/preload_translations.py --terms --limit 1000
  python scripts/preload_translations.py --terms --all

  # Descriptions (LLM translation):
  python scripts/preload_translations.py --descriptions --api-key sk-xxx
  python scripts/preload_translations.py --descriptions --api-key sk-xxx --api-base https://api.openai.com/v1 --model gpt-4o-mini
  python scripts/preload_translations.py --descriptions --api-key sk-xxx --batch-size 50 --limit 500

  # Both:
  python scripts/preload_translations.py --terms --descriptions --api-key sk-xxx
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

# ─── TERM_DICT (duplicated from app/api/v1/translate.py to avoid cross-module import) ───
TERM_DICT = {
    "Thematic": "主題", "Strategy": "策略", "Party": "派對", "Family": "家庭",
    "Abstract": "抽象", "Cooperative": "合作", "Economic": "經濟", "Negotiation": "談判",
    "Adventure": "冒險", "Puzzle": "解謎", "Medical": "醫療", "Science Fiction": "科幻",
    "Fantasy": "奇幻", "Horror": "恐怖", "Humor": "幽默", "Deduction": "推理",
    "Exploration": "探索", "Territory Building": "領地建設", "Civilization": "文明",
    "Farming": "農場", "Industry / Manufacturing": "工業", "Transportation": "運輸",
    "Train": "火車", "Renaissance": "文藝復興", "Ancient": "古代", "Medieval": "中世紀",
    "Modern": "現代", "Post-Napoleonic": "後拿破崙", "World War I": "一戰",
    "World War II": "二戰", "Prehistoric": "史前", "Nautical": "航海",
    "Spies/Secret Agents": "間諜", "Zombies": "殭屍", "Movies / TV / Radio": "影視",
    "Music": "音樂", "Book": "書籍", "Comic Book / Strip": "漫畫",
    "Video Game": "電子遊戲", "Sports": "運動", "Racing": "競速",
    "Fighting": "格鬥", "Miniatures": "微縮", "Card Game": "卡牌遊戲",
    "Collectible Components": "收藏組件", "Bluffing": "唬弄", "Dice": "骰子",
    "Children's Game": "兒童遊戲", "Educational": "教育", "Math": "數學",
    "Memory": "記憶", "Number": "數字", "Real-time": "即時", "Simultaneous": "同步",
    "Singing": "歌唱", "Word Game": "文字遊戲", "Trivia": "冷知識",
    "Worker Placement": "工人放置", "Deck Building": "牌組構築", "Dice Rolling": "擲骰",
    "Tile Placement": "板塊放置", "Auction": "競標", "Drafting": "輪抽",
    "Set Collection": "套組收集", "Area Control": "區域控制", "Hidden Roles": "隱藏身分",
    "Push Your Luck": "碰運氣", "Role Playing": "角色扮演", "Storytelling": "說故事",
    "Voting": "投票", "Simultaneous Action Selection": "同時行動選擇",
    "Action Points": "行動點數", "Area Movement": "區域移動", "Area-Impulse": "區域脈衝",
    "Betting": "下注", "Campaign": "戰役", "Chit-Pull System": "標記抽取",
    "Closed Economy": "封閉經濟", "Command Cards": "指令卡", "Connections": "連線",
    "Conspiracy": "陰謀", "Crayon Rail System": "蠟筆鐵路", "Critical Hits": "暴擊",
    "Deck Construction": "牌組構建", "Grid Movement": "格線移動",
    "Hex-and-Counter": "六角格", "Line Drawing": "畫線", "Loans": "貸款",
    "Mancala": "播棋", "Map Addition": "地圖加成", "Market": "市場",
    "Matching": "配對", "Measurement Movement": "測量移動", "Melding": "融合",
    "Modular Board": "模組化圖板", "Move Through Deck": "穿牌組",
    "Narrative Choice": "敘事選擇", "Network Building": "網路建設",
    "Once-Per-Game Abilities": "每局一次", "Ownership": "所有權",
    "Pattern Building": "圖案構建", "Pattern Recognition": "圖案識別",
    "Physical Removal": "實體移除", "Pick-up and Deliver": "取送",
    "Player Elimination": "玩家淘汰", "Point to Point Movement": "點對點移動",
    "Pre-constructed Deck": "預構牌組", "Press Your Luck": "碰運氣",
    "Randomized Setup": "隨機設置", "Ratio / Combat Results Table": "戰果表",
    "Re-rolling": "重擲", "Rondel": "輪盤", "Route Building": "路線建設",
    "Sandbox": "沙盒", "Secret Unit Deployment": "秘密部署",
    "Semi-Cooperative Game": "半合作", "Stacking": "堆疊", "Stock Holding": "持股",
    "Take That": "突襲", "Tech Trees": "科技樹", "Time Track": "時間軌",
    "Track Movement": "軌道移動", "Trading": "交易", "Trick-Taking": "吃墩",
    "Variable Phase Order": "可變階段順序", "Variable Player Powers": "可變玩家能力",
    "Victory Points": "勝利點數", "Action Drafting": "行動輪抽",
    "Action Queue": "行動佇列", "Advantage Token": "優勢標記",
    "Bribery": "賄賂", "Catch Up": "追趕", "Communication Limits": "溝通限制",
    "End Game Bonuses": "終局獎勵", "Flicking": "彈射", "Follow": "跟隨",
    "Force Commitment": "兵力投入", "Increase Value of Unchosen Resources": "未選資源增值",
    "Kill Steal": "搶怪", "Layering": "分層", "Locks": "鎖定",
    "Map Deformation": "地圖變形", "Maze": "迷宮", "Minimap": "小地圖",
    "Order Counters": "指令標記", "Placement / Stacking": "放置/堆疊",
    "Slide/Push": "滑動/推動", "Snaking": "蛇形", "Speed Matching": "快速配對",
    "Sudden Death": "突然死亡", "Targeting": "瞄準", "Team-Based Game": "團隊遊戲",
    "Tug of War": "拔河", "Turn Order: Auction": "回合順序：競標",
    "Turn Order: Claim Action": "回合順序：宣告", "Turn Order: Pass Order": "回合順序：傳遞",
    "Turn Order: Progressive": "回合順序：遞增", "Turn Order: Random": "回合順序：隨機",
    "Turn Order: Stat-Based": "回合順序：屬性",
}

# ─── LLM translation constants ───
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


# ═══════════════════════════════════════════════════════════════
#  TERMS MODE (deterministic, no API)
# ═══════════════════════════════════════════════════════════════

async def preload_terms(limit: int | None = None, all_games: bool = False) -> dict:
    """Translate categories.name_zh and mechanics.name_zh using TERM_DICT."""
    terms = list(TERM_DICT.keys())

    query = {
        "$or": [
            {"categories.name": {"$in": terms}},
            {"categories": {"$in": terms}},
            {"mechanics.name": {"$in": terms}},
            {"mechanics": {"$in": terms}},
        ],
    }
    projection = {"bgg_id": 1, "categories": 1, "mechanics": 1}

    cursor = mongo_db.board_games.find(query, projection)
    if not all_games and limit:
        cursor = cursor.limit(limit)

    games = await cursor.to_list(length=limit or 0)
    total = len(games)
    print(f"Games with translatable terms: {total}")

    updated = 0
    for i, doc in enumerate(games, 1):
        updates: dict = {}

        if doc.get("categories"):
            new_cats = []
            for c in doc["categories"]:
                cname = c["name"] if isinstance(c, dict) else c
                cid = c.get("id", 0) if isinstance(c, dict) else 0
                translated = TERM_DICT.get(cname)
                new_cats.append({
                    "id": cid,
                    "name": cname,
                    "name_zh": translated or cname,
                })
            updates["categories"] = new_cats

        if doc.get("mechanics"):
            new_mechs = []
            for m in doc["mechanics"]:
                mname = m["name"] if isinstance(m, dict) else m
                mid = m.get("id", 0) if isinstance(m, dict) else 0
                translated = TERM_DICT.get(mname)
                new_mechs.append({
                    "id": mid,
                    "name": mname,
                    "name_zh": translated or mname,
                })
            updates["mechanics"] = new_mechs

        if updates:
            await mongo_db.board_games.update_one(
                {"bgg_id": doc["bgg_id"]},
                {"$set": updates},
            )
            updated += 1

        if i % 200 == 0 or i == total:
            print(f"  [{i}/{total}] updated={updated}")

    return {"total": total, "updated": updated}


# ═══════════════════════════════════════════════════════════════
#  DESCRIPTIONS MODE (LLM API)
# ═══════════════════════════════════════════════════════════════

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
    do_terms = args.terms
    do_descs = args.descriptions

    if not do_terms and not do_descs:
        # Default: both if api-key provided, otherwise terms only
        do_terms = True
        do_descs = bool(args.api_key)

    if do_terms:
        print("\n" + "=" * 60)
        print("  TERMS TRANSLATION (deterministic, no API)")
        print("=" * 60)
        result = await preload_terms(limit=args.limit, all_games=args.all_games)
        print(f"\nTerms result: {result}")

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
    parser.add_argument("--terms", action="store_true", help="Translate categories/mechanics terms (deterministic, no API)")
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

    print(f"Preload translations config: terms={args.terms} descriptions={args.descriptions} limit={args.limit} all={args.all_games}")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
