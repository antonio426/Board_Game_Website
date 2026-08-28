import re
from fastapi import APIRouter, Query
from app.core.database import mongo_db

router = APIRouter(prefix="/translate", tags=["translate"])

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


@router.post("/terms")
async def translate_terms_endpoint(batch_size: int = Query(100, ge=1, le=500)):
    return await translate_terms(batch_size)


async def translate_terms(batch_size: int = 100):
    games = []
    terms = list(TERM_DICT.keys())
    cursor = mongo_db.board_games.find(
        {"$or": [
            {"categories.name": {"$in": terms}},
            {"categories": {"$in": terms}},
            {"mechanics.name": {"$in": terms}},
            {"mechanics": {"$in": terms}},
        ]},
        {"bgg_id": 1, "categories": 1, "mechanics": 1},
    ).limit(batch_size)
    async for doc in cursor:
        games.append(doc)

    updated = 0
    for doc in games:
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

    return {"status": "ok", "processed": len(games), "updated": updated}


@router.post("/descriptions")
async def translate_descriptions(batch_size: int = Query(10, ge=1, le=100)):
    cursor = mongo_db.board_games.find(
        {"description_en": {"$ne": ""}, "description_zh": ""},
        {"bgg_id": 1, "name_en": 1, "description_en": 1},
    ).limit(batch_size)

    games = []
    async for doc in cursor:
        games.append(doc)

    return {
        "status": "ok",
        "pending_count": len(games),
        "message": "Description translation requires LLM API. Use /translate/terms for immediate term translation.",
        "pending_games": [{"bgg_id": g["bgg_id"], "name_en": g.get("name_en", "")} for g in games],
    }
