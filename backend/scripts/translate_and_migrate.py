#!/usr/bin/env python3
"""Translate board game category & mechanic names to 繁體中文 (Traditional Chinese)
via hardcoded dictionaries, create mapping collections, then bulk-migrate
string arrays to object format.

NO OpenAI / LLM call. NO API key required. All translations are
established Taiwanese board game terminology baked into this script.

Usage:
    cd backend
    source .venv/bin/activate
    python scripts/translate_and_migrate.py --dry-run   # preview only, no DB writes
    python scripts/translate_and_migrate.py              # full run
    python scripts/translate_and_migrate.py --dry-run --out-dir /tmp/preview
"""

import os
import sys
import json
import argparse
from pathlib import Path

from pymongo import MongoClient, UpdateOne

MONGO_URI = os.getenv("MONGO_URI", "mongodb://boardgame:boardgame_dev@localhost:27017")
DB_NAME = "boardgame"
COLLECTION = "board_games"


# ═══════════════════════════════════════════════════════════════════════════
#  HARDCODED TRANSLATION DICTIONARIES (繁體中文 / Taiwanese board game terms)
# ═══════════════════════════════════════════════════════════════════════════

CATEGORY_ZH: dict[str, str] = {
    "Abstract Strategy": "抽象策略",
    "Action / Dexterity": "動作／敏捷",
    "Adventure": "冒險",
    "Age of Reason": "理性時代",
    "American Civil War": "美國南北戰爭",
    "American Indian Wars": "美洲印第安戰爭",
    "American Revolutionary War": "美國獨立戰爭",
    "American West": "美國西部",
    "Ancient": "古代",
    "Animals": "動物",
    "Arabian": "阿拉伯",
    "Aviation / Flight": "航空／飛行",
    "Bluffing": "唬弄",
    "Book": "書籍",
    "Card Game": "卡牌遊戲",
    "Children's Game": "兒童遊戲",
    "City Building": "城市建設",
    "Civil War": "內戰",
    "Civilization": "文明",
    "Collectible Components": "收藏組件",
    "Comic Book / Strip": "漫畫／連環圖",
    "Deduction": "推理",
    "Dice": "骰子",
    "Economic": "經濟",
    "Educational": "教育",
    "Electronic": "電子",
    "Environmental": "環境",
    "Expansion for Base-game": "基礎遊戲擴充",
    "Exploration": "探索",
    "Fan Expansion": "粉絲擴充",
    "Fantasy": "奇幻",
    "Farming": "農場",
    "Fighting": "格鬥",
    "Game System": "遊戲系統",
    "Horror": "恐怖",
    "Humor": "幽默",
    "Industry / Manufacturing": "工業／製造",
    "Korean War": "韓戰",
    "Mafia": "黑手黨",
    "Math": "數學",
    "Mature / Adult": "成人",
    "Maze": "迷宮",
    "Medical": "醫療",
    "Medieval": "中世紀",
    "Memory": "記憶",
    "Miniatures": "微縮模型",
    "Modern Warfare": "現代戰爭",
    "Movies / TV / Radio theme": "電影／電視／廣播主題",
    "Murder / Mystery": "謀殺／神秘",
    "Music": "音樂",
    "Mythology": "神話",
    "Napoleonic": "拿破崙時代",
    "Nautical": "航海",
    "Negotiation": "談判",
    "Novel-based": "小說改編",
    "Number": "數字",
    "Party Game": "派對遊戲",
    "Pike and Shot": "長矛與火槍",
    "Pirates": "海盜",
    "Political": "政治",
    "Post-Napoleonic": "後拿破崙時代",
    "Prehistoric": "史前",
    "Print & Play": "列印即玩",
    "Puzzle": "解謎",
    "Racing": "競速",
    "Real-time": "即時",
    "Religious": "宗教",
    "Renaissance": "文藝復興",
    "Science Fiction": "科幻",
    "Space Exploration": "太空探索",
    "Spies / Secret Agents": "間諜／秘密特務",
    "Sports": "運動",
    "Territory Building": "領土建設",
    "Third-party Expansion": "第三方擴充",
    "Trains": "火車",
    "Transportation": "運輸",
    "Travel": "旅行",
    "Trivia": "冷知識",
    "Video Game Theme": "電子遊戲主題",
    "Vietnam War": "越戰",
    "Wargame": "戰棋",
    "Word Game": "文字遊戲",
    "World War I": "第一次世界大戰",
    "World War II": "第二次世界大戰",
    "Zombies": "殭屍",
}


MECHANIC_ZH: dict[str, str] = {
    "Acting": "演技",
    "Action / Event": "行動／事件",
    "Action Drafting": "行動輪抽",
    "Action Points": "行動點數",
    "Action Queue": "行動佇列",
    "Action Retrieval": "行動回收",
    "Action Timer": "行動計時",
    "Advantage Token": "優勢標記",
    "Algorithmic Resolution": "演算法判定",
    "Alliances": "聯盟",
    "Area Majority / Influence": "區域多數／影響力",
    "Area Movement": "區域移動",
    "Area-Impulse": "區域脈衝",
    "Auction / Bidding": "競標／出價",
    "Auction Compensation": "競標補償",
    "Auction: Dexterity": "競標：體能",
    "Auction: Dutch": "競標：荷蘭式",
    "Auction: Dutch Priority": "競標：荷蘭式優先",
    "Auction: English": "競標：英式",
    "Auction: Fixed Placement": "競標：固定位置",
    "Auction: Multiple Lot": "競標：多重組合",
    "Auction: Once Around": "競標：單輪",
    "Auction: Sealed Bid": "競標：密封出價",
    "Auction: Turn Order Until Pass": "競標：回合順序直到棄標",
    "Automatic Resource Growth": "自動資源增長",
    "Betting and Bluffing": "下注與唬弄",
    "Bias": "偏誤",
    "Bids As Wagers": "出價作為賭注",
    "Bingo": "賓果",
    "Bribery": "賄賂",
    "Campaign / Battle Card Driven": "戰役／戰鬥卡驅動",
    "Card Play Conflict Resolution": "卡牌玩法衝突解決",
    "Catch the Leader": "追趕領先者",
    "Chaining": "連鎖",
    "Chit-Pull System": "標記抽取系統",
    "Closed Drafting": "封閉輪抽",
    "Closed Economy Auction": "封閉經濟競標",
    "Command Cards": "指令卡",
    "Commodity Speculation": "商品投機",
    "Communication Limits": "溝通限制",
    "Connections": "連線",
    "Constrained Bidding": "限制出價",
    "Contracts": "合約",
    "Cooperative Game": "合作遊戲",
    "Crayon Rail System": "蠟筆鐵路系統",
    "Critical Hits and Failures": "暴擊與失敗",
    "Cube Tower": "方塊塔",
    "Deck Construction": "牌組構築",
    "Deck, Bag, and Pool Building": "牌組、袋與池構築",
    "Deduction": "推理",
    "Delayed Purchase": "延遲購買",
    "Dice Rolling": "擲骰",
    "Die Icon Resolution": "骰面圖示判定",
    "Different Dice Movement": "不同骰子移動",
    "Drawing": "繪圖",
    "Elapsed Real Time Ending": "經過實際時間結束",
    "Enclosure": "圍欄",
    "End Game Bonuses": "終局獎勵",
    "Events": "事件",
    "Facing": "朝向",
    "Finale Ending": "終幕結束",
    "Flicking": "彈射",
    "Follow": "跟隨",
    "Force Commitment": "兵力投入",
    "Grid Coverage": "格線覆蓋",
    "Grid Movement": "格線移動",
    "Hand Management": "手牌管理",
    "Hexagon Grid": "六角格",
    "Hidden Movement": "隱藏移動",
    "Hidden Roles": "隱藏身分",
    "Hidden Victory Points": "隱藏勝利點數",
    "Highest-Lowest Scoring": "最高最低計分",
    "Hot Potato": "燙手山芋",
    "I Cut, You Choose": "我切你選",
    "Impulse Movement": "脈衝移動",
    "Income": "收入",
    "Increase Value of Unchosen Resources": "未選資源增值",
    "Induction": "歸納",
    "Interrupts": "中斷",
    "Investment": "投資",
    "Kill Steal": "搶尾刀",
    "King of the Hill": "山頭之王",
    "Ladder Climbing": "爬梯",
    "Lane Battler": "車道戰鬥",
    "Layering": "分層",
    "Legacy Game": "傳承遊戲",
    "Line Drawing": "畫線",
    "Line of Sight": "視線",
    "Loans": "貸款",
    "Lose a Turn": "跳過回合",
    "Mancala": "播棋",
    "Map Addition": "地圖擴充",
    "Map Deformation": "地圖變形",
    "Map Reduction": "地圖縮減",
    "Market": "市場",
    "Matching": "配對",
    "Measurement Movement": "測量移動",
    "Melding and Splaying": "融合與展開",
    "Memory": "記憶",
    "Minimap Resolution": "小地圖判定",
    "Modular Board": "模組化圖板",
    "Move Through Deck": "穿牌組移動",
    "Movement Points": "移動點數",
    "Movement Template": "移動模板",
    "Moving Multiple Units": "多單位移動",
    "Multi-Use Cards": "多用途卡",
    "Multiple Maps": "多張地圖",
    "Narrative Choice / Paragraph": "敘事選擇／段落",
    "Negotiation": "談判",
    "Neighbor Scope": "鄰接範圍",
    "Network and Route Building": "網路與路線建設",
    "Once-Per-Game Abilities": "每局一次能力",
    "Open Drafting": "開放輪抽",
    "Order Counters": "指令標記",
    "Ordering": "排序",
    "Ownership": "所有權",
    "Paper-and-Pencil": "紙筆",
    "Passed Action Token": "傳遞行動標記",
    "Pattern Building": "圖案構建",
    "Pattern Movement": "圖案移動",
    "Pattern Recognition": "圖案識別",
    "Physical Removal": "實體移除",
    "Pick-up and Deliver": "取送",
    "Pieces as Map": "棋子即地圖",
    "Player Elimination": "玩家淘汰",
    "Player Judge": "玩家裁判",
    "Point to Point Movement": "點對點移動",
    "Predictive Bid": "預測出價",
    "Prisoner's Dilemma": "囚徒困境",
    "Programmed Movement": "程式化移動",
    "Push Your Luck": "碰運氣",
    "Questions and Answers": "問與答",
    "Race": "競速",
    "Random Production": "隨機生產",
    "Ratio / Combat Results Table": "戰果表",
    "Re-rolling and Locking": "重擲與鎖定",
    "Real-Time": "即時",
    "Relative Movement": "相對移動",
    "Resource Queue": "資源佇列",
    "Resource to Move": "資源換移動",
    "Rock-Paper-Scissors": "剪刀石頭布",
    "Role Playing": "角色扮演",
    "Roles with Asymmetric Information": "不對稱資訊角色",
    "Roll / Spin and Move": "擲骰／轉盤移動",
    "Rondel": "輪盤",
    "Scenario / Mission / Campaign Game": "劇本／任務／戰役遊戲",
    "Score-and-Reset Game": "計分重置遊戲",
    "Secret Unit Deployment": "秘密部署",
    "Selection Order Bid": "選擇順序出價",
    "Semi-Cooperative Game": "半合作遊戲",
    "Set Collection": "套組收集",
    "Simulation": "模擬",
    "Simultaneous Action Selection": "同時行動選擇",
    "Singing": "歌唱",
    "Single Loser Game": "單一輸家遊戲",
    "Single Play": "單次使用",
    "Slide / Push": "滑動／推動",
    "Solo / Solitaire Game": "單人遊戲",
    "Speed Matching": "快速配對",
    "Spelling": "拼字",
    "Square Grid": "方格",
    "Stacking and Balancing": "堆疊與平衡",
    "Stat Check Resolution": "屬性檢定",
    "Static Capture": "靜態奪取",
    "Stock Holding": "持股",
    "Storytelling": "說故事",
    "Sudden Death Ending": "突然死亡結束",
    "Tags": "標記",
    "Take That": "突襲",
    "Targeted Clues": "目標線索",
    "Team-Based Game": "團隊遊戲",
    "Tech Trees / Tech Tracks": "科技樹／科技軌",
    "Three Dimensional Movement": "三維移動",
    "Tile Placement": "板塊放置",
    "Track Movement": "軌道移動",
    "Trading": "交易",
    "Traitor Game": "叛徒遊戲",
    "Trick-taking": "吃墩",
    "Tug of War": "拔河",
    "Turn Order: Auction": "回合順序：競標",
    "Turn Order: Claim Action": "回合順序：宣告行動",
    "Turn Order: Pass Order": "回合順序：傳遞",
    "Turn Order: Progressive": "回合順序：遞增",
    "Turn Order: Random": "回合順序：隨機",
    "Turn Order: Role Order": "回合順序：角色順序",
    "Turn Order: Stat-Based": "回合順序：屬性",
    "Turn Order: Time Track": "回合順序：時間軌",
    "Variable Phase Order": "可變階段順序",
    "Variable Player Powers": "可變玩家能力",
    "Variable Set-up": "可變設置",
    "Victory Points as a Resource": "勝利點數作為資源",
    "Voting": "投票",
    "Worker Placement": "工人放置",
    "Worker Placement with Dice Workers": "工人放置：骰子工人",
    "Worker Placement, Different Worker Types": "工人放置：不同工人類型",
    "Zone of Control": "控制區域",
}


# ═══════════════════════════════════════════════════════════════════════════
#  MongoDB helpers
# ═══════════════════════════════════════════════════════════════════════════

def get_unique_names(db, field: str) -> list[str]:
    """Get unique string names from a field that contains string arrays."""
    pipeline = [
        {"$match": {field: {"$type": "array", "$ne": []}}},
        {"$project": {field: 1}},
        {"$unwind": f"${field}"},
        {"$match": {field: {"$type": "string"}}},
        {"$group": {"_id": f"${field}"}},
        {"$sort": {"_id": 1}},
    ]
    return [doc["_id"] for doc in db[COLLECTION].aggregate(pipeline, allowDiskUse=True)]


def lookup_translations(names: list[str], dictionary: dict[str, str], kind: str) -> tuple[dict[str, str], list[str]]:
    """Look up every name in the hardcoded dictionary. Returns (translations, missing)."""
    translations: dict[str, str] = {}
    missing: list[str] = []
    for name in names:
        zh = dictionary.get(name)
        if zh:
            translations[name] = zh
        else:
            missing.append(name)
            translations[name] = name  # fallback to English
    return translations, missing


def build_mapping_collection(db, coll_name: str, names: list[str], translations: dict[str, str]) -> dict:
    """Create or replace a mapping collection with {id, name, name_zh} docs."""
    docs = []
    for i, name in enumerate(names, start=1):
        docs.append({
            "id": i,
            "name": name,
            "name_zh": translations.get(name, name),
        })
    db[coll_name].drop()
    if docs:
        db[coll_name].insert_many(docs)
    print(f"  Created {coll_name}: {len(docs)} docs")
    return {d["name"]: d for d in docs}


def bulk_migrate_strings(db, field: str, mapping: dict) -> int:
    """
    Migrate all documents where `field` is a string array
    to object array format [{id, name, name_zh}, ...].
    """
    query = {f"{field}.0": {"$type": "string"}}

    cursor = db[COLLECTION].find(query, {"_id": 1, field: 1}, batch_size=5000)
    ops = []
    converted = 0
    skipped = 0

    for doc in cursor:
        arr = doc.get(field, [])
        if not any(isinstance(x, str) for x in arr):
            skipped += 1
            continue

        new_arr = []
        for item in arr:
            if isinstance(item, str):
                entry = mapping.get(item)
                if entry:
                    new_arr.append({
                        "id": entry["id"],
                        "name": entry["name"],
                        "name_zh": entry["name_zh"],
                    })
                else:
                    # Unknown name — keep as object with id=0
                    new_arr.append({"id": 0, "name": item, "name_zh": item})
            elif isinstance(item, dict):
                new_arr.append(item)  # already object format
            else:
                continue

        ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {field: new_arr}}))
        converted += 1

        if len(ops) >= 2000:
            db[COLLECTION].bulk_write(ops, ordered=False)
            ops = []

    if ops:
        db[COLLECTION].bulk_write(ops, ordered=False)

    print(f"  Migrated {field}: {converted} docs updated, {skipped} skipped (already objects)")
    return converted


# ═══════════════════════════════════════════════════════════════════════════
#  Verification
# ═══════════════════════════════════════════════════════════════════════════

def verify(db) -> None:
    """Print post-migration sanity checks."""
    print("\n=== Verify ===")
    remaining_cats = db[COLLECTION].count_documents({"categories.0": {"$type": "string"}})
    remaining_mechs = db[COLLECTION].count_documents({"mechanics.0": {"$type": "string"}})
    print(f"  Remaining docs with string categories: {remaining_cats}")
    print(f"  Remaining docs with string mechanics:  {remaining_mechs}")

    cat_coll_size = db["bgg_categories"].count_documents({})
    mech_coll_size = db["bgg_mechanics"].count_documents({})
    print(f"  bgg_categories size: {cat_coll_size}")
    print(f"  bgg_mechanics size:  {mech_coll_size}")

    sample = db[COLLECTION].find_one(
        {"categories.0": {"$type": "object"}},
        {"_id": 0, "name_en": 1, "categories": 1, "mechanics": 1},
    )
    if sample:
        print(f"\n  Sample migrated doc ({sample.get('name_en', '?')}):")
        print(f"    categories: {json.dumps(sample.get('categories', [])[:3], ensure_ascii=False)}")
        print(f"    mechanics:  {json.dumps(sample.get('mechanics', [])[:3], ensure_ascii=False)}")

    # Any docs still with mixed types (some string, some dict)?
    mixed_cat = db[COLLECTION].count_documents({
        "categories": {"$elemMatch": {"$type": "string"}},
        "categories.0": {"$type": "object"},
    })
    mixed_mech = db[COLLECTION].count_documents({
        "mechanics": {"$elemMatch": {"$type": "string"}},
        "mechanics.0": {"$type": "object"},
    })
    print(f"  Docs with mixed string/object in categories: {mixed_cat}")
    print(f"  Docs with mixed string/object in mechanics:  {mixed_mech}")


# ═══════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Translate category/mechanic names to 繁體中文 via hardcoded dict, migrate to object arrays",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Translate + write JSON files to --out-dir; skip DB writes")
    parser.add_argument("--out-dir", type=str, default="/tmp",
                        help="Directory for dry-run JSON dumps (default: /tmp)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"MONGO_URI: {MONGO_URI}")
    print(f"DB:        {DB_NAME}")
    print(f"COLL:      {COLLECTION}")
    print(f"Mode:      {'DRY RUN' if args.dry_run else 'LIVE'}")

    mongo = MongoClient(MONGO_URI)
    db = mongo[DB_NAME]

    total_games = db[COLLECTION].count_documents({})
    print(f"Total games: {total_games}")

    # ── Step 1: Collect unique names ──────────────────────────────────────
    print("\n=== Step 1: Collect unique category/mechanic names ===")
    cat_names = get_unique_names(db, "categories")
    mech_names = get_unique_names(db, "mechanics")
    print(f"  Unique categories in DB: {len(cat_names)}")
    print(f"  Unique mechanics in DB:  {len(mech_names)}")
    print(f"  Hardcoded CATEGORY_ZH size:  {len(CATEGORY_ZH)}")
    print(f"  Hardcoded MECHANIC_ZH size:  {len(MECHANIC_ZH)}")

    # ── Step 2: Translate via hardcoded dicts ────────────────────────────
    print("\n=== Step 2: Translate via hardcoded dictionaries ===")
    cat_translations, cat_missing = lookup_translations(cat_names, CATEGORY_ZH, "category")
    mech_translations, mech_missing = lookup_translations(mech_names, MECHANIC_ZH, "mechanic")

    print(f"  Categories: {len(cat_translations)} translated, {len(cat_missing)} missing (fell back to English)")
    if cat_missing:
        print("    Missing category keys:")
        for m in cat_missing:
            print(f"      - {m!r}")

    print(f"  Mechanics:  {len(mech_translations)} translated, {len(mech_missing)} missing (fell back to English)")
    if mech_missing:
        print("    Missing mechanic keys:")
        for m in mech_missing:
            print(f"      - {m!r}")

    # Sample translations
    print("\n  Sample category translations:")
    for name in cat_names[:10]:
        print(f"    {name} → {cat_translations.get(name, '?')}")
    print("\n  Sample mechanic translations:")
    for name in mech_names[:10]:
        print(f"    {name} → {mech_translations.get(name, '?')}")

    # ── Step 2.5: Dry-run output ─────────────────────────────────────────
    if args.dry_run:
        cat_path = out_dir / "category_translations.json"
        mech_path = out_dir / "mechanic_translations.json"
        cat_path.write_text(
            json.dumps(cat_translations, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        mech_path.write_text(
            json.dumps(mech_translations, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("\n[DRY RUN] Stopping before migration.")
        print(f"  Saved: {cat_path}")
        print(f"  Saved: {mech_path}")
        return

    # ── Step 3: Create mapping collections ──────────────────────────────
    print("\n=== Step 3: Create mapping collections ===")
    cat_mapping = build_mapping_collection(db, "bgg_categories", cat_names, cat_translations)
    mech_mapping = build_mapping_collection(db, "bgg_mechanics", mech_names, mech_translations)

    # ── Step 4: Bulk migrate string arrays → object arrays ─────────────
    print("\n=== Step 4: Bulk migrate string arrays ===")
    print("  Migrating categories...")
    bulk_migrate_strings(db, "categories", cat_mapping)
    print("  Migrating mechanics...")
    bulk_migrate_strings(db, "mechanics", mech_mapping)

    # ── Step 5: Verify ──────────────────────────────────────────────────
    verify(db)

    print("\nDone: Migration complete!")


if __name__ == "__main__":
    main()
