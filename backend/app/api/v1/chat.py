import json
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.database import mongo_db
from app.recommenders.content_based import ContentBasedRecommender
from app.recommenders.hybrid import HybridRecommender

router = APIRouter(prefix="/chat", tags=["chat"])

_cb = ContentBasedRecommender()
_hybrid = HybridRecommender()


class ChatMessage(BaseModel):
    message: str
    locale: str = "zh"


SYSTEM_PROMPT_ZH = """你是桌遊推薦顧問。根據使用者需求，從資料庫搜尋合適的桌遊並給出推薦。
回答格式：簡短推薦理由 + 遊戲名稱（附BGG ID）。可推薦多款。"""

SYSTEM_PROMPT_EN = """You are a board game recommendation advisor. Based on user needs, search the database for suitable games and give recommendations.
Format: brief reason + game name (with BGG ID). You can recommend multiple games."""


async def _search_games(query: str, limit: int = 8) -> list[dict]:
    conditions = []
    tokens = query.lower().replace("，", " ").replace(",", " ").split()
    for token in tokens:
        if token:
            conditions.append({
                "$or": [
                    {"name_en": {"$regex": token, "$options": "i"}},
                    {"name_zh": {"$regex": token, "$options": "i"}},
                    {"categories.name": {"$regex": token, "$options": "i"}},
                    {"categories.name_zh": {"$regex": token, "$options": "i"}},
                    {"mechanics.name": {"$regex": token, "$options": "i"}},
                    {"mechanics.name_zh": {"$regex": token, "$options": "i"}},
                    {"designers": {"$regex": token, "$options": "i"}},
                ]
            })

    if not conditions:
        cursor = mongo_db.board_games.find({"name_en": {"$not": {"$regex": r"^Board Game #"}}}).sort("bgg_rating", -1).limit(limit)
    else:
        cursor = mongo_db.board_games.find({"$and": conditions, "name_en": {"$not": {"$regex": r"^Board Game #"}}}).sort("bgg_rating", -1).limit(limit)

    games = []
    async for doc in cursor:
        games.append({
            "bgg_id": doc["bgg_id"],
            "name_en": doc.get("name_en", ""),
            "name_zh": doc.get("name_zh", ""),
            "bgg_rating": doc.get("bgg_rating", 0),
            "bgg_weight": doc.get("bgg_weight", 0),
            "min_players": doc.get("min_players", 0),
            "max_players": doc.get("max_players", 0),
            "min_playtime": doc.get("min_playtime", 0),
            "max_playtime": doc.get("max_playtime", 0),
            "categories": [c["name"] for c in doc.get("categories", [])],
            "mechanics": [m["name"] for m in doc.get("mechanics", [])],
        })
    return games


async def _context_search(players: int | None, playtime: int | None, max_weight: float | None, category: str | None, mechanic: str | None, limit: int = 8) -> list[dict]:
    fq: dict = {}
    if players:
        fq["min_players"] = {"$lte": players}
        fq["max_players"] = {"$gte": players}
    if playtime:
        fq["min_playtime"] = {"$lte": playtime}
    if max_weight:
        fq["bgg_weight"] = {"$lte": max_weight}
    if category:
        fq["categories.name"] = {"$regex": category, "$options": "i"}
    if mechanic:
        fq["mechanics.name"] = {"$regex": mechanic, "$options": "i"}

    cursor = mongo_db.board_games.find({**fq, "name_en": {"$not": {"$regex": r"^Board Game #"}}}).sort("bgg_rating", -1).limit(limit)
    games = []
    async for doc in cursor:
        games.append({
            "bgg_id": doc["bgg_id"],
            "name_en": doc.get("name_en", ""),
            "name_zh": doc.get("name_zh", ""),
            "bgg_rating": doc.get("bgg_rating", 0),
            "bgg_weight": doc.get("bgg_weight", 0),
            "min_players": doc.get("min_players", 0),
            "max_players": doc.get("max_players", 0),
            "min_playtime": doc.get("min_playtime", 0),
            "max_playtime": doc.get("max_playtime", 0),
            "categories": [c["name"] for c in doc.get("categories", [])],
            "mechanics": [m["name"] for m in doc.get("mechanics", [])],
        })
    return games


def _parse_intent(message: str) -> dict:
    import re
    msg = message.lower()
    intent = {"players": None, "playtime": None, "max_weight": None, "category": None, "mechanic": None, "similar_to": None}

    player_match = re.search(r"(\d+)\s*(人|player|players|人玩)", msg)
    if player_match:
        intent["players"] = int(player_match.group(1))

    time_match = re.search(r"(\d+)\s*(分鐘|min|minute)", msg)
    if time_match:
        intent["playtime"] = int(time_match.group(1))

    if any(w in msg for w in ["轻", "簡單", "light", "簡", "简单"]):
        intent["max_weight"] = 2.5
    elif any(w in msg for w in ["重", "复杂", "heavy", "complex", "深度"]):
        intent["max_weight"] = 5.0

    cat_map = {
        "合作": "Cooperative", "cooperative": "Cooperative", "派對": "Party", "party": "Party",
        "策略": "Strategy", "strategy": "Strategy", "家庭": "Family", "family": "Family",
        "抽象": "Abstract", "abstract": "Abstract", "經濟": "Economic", "economic": "Economic",
        "冒险": "Adventure", "adventure": "Adventure", "解谜": "Puzzle", "puzzle": "Puzzle",
        "主题": "Thematic", "thematic": "Thematic", "谈判": "Negotiation", "negotiation": "Negotiation",
        "醫療": "Medical", "medical": "Medical", "科幻": "Science Fiction",
    }
    for k, v in cat_map.items():
        if k in msg:
            intent["category"] = v
            break

    mech_map = {
        "工人": "Worker Placement", "worker": "Worker Placement",
        "牌組": "Deck Building", "deck": "Deck Building",
        "骰子": "Dice Rolling", "dice": "Dice Rolling",
        "競標": "Auction", "auction": "Auction",
        "選牌": "Drafting", "draft": "Drafting",
        "區控": "Area Control", "area control": "Area Control",
        "隱藏": "Hidden Roles", "hidden": "Hidden Roles",
    }
    for k, v in mech_map.items():
        if k in msg:
            intent["mechanic"] = v
            break

    like_match = re.search(r"像(.+?)(的|一樣|like)", msg)
    if like_match:
        intent["similar_to"] = like_match.group(1).strip()

    return intent


def _format_games(games: list[dict], locale: str) -> str:
    if not games:
        return "No matching games found." if locale == "en" else "找不到符合的遊戲。"

    lines = []
    for g in games:
        name = g["name_zh"] or g["name_en"] if locale == "zh" else g["name_en"]
        info = f"★{g['bgg_rating']} · {g['min_players']}-{g['max_players']}人 · {g['min_playtime']}-{g['max_playtime']}min"
        cats = ", ".join(g["categories"][:3])
        lines.append(f"- **{name}** (BGG#{g['bgg_id']}): {info} | {cats}")
    return "\n".join(lines)


@router.post("/recommend")
async def chat_recommend(msg: ChatMessage):
    intent = _parse_intent(msg.message)

    games = []
    if intent.get("similar_to"):
        name_query = intent["similar_to"]
        doc = await mongo_db.board_games.find_one({
            "$or": [
                {"name_en": {"$regex": name_query, "$options": "i"}},
                {"name_zh": {"$regex": name_query, "$options": "i"}},
            ]
        })
        if doc:
            similar = await _hybrid.get_similar_with_data(doc["bgg_id"], top_k=5)
            for s in similar:
                games.append({
                    "bgg_id": s["bgg_id"],
                    "name_en": s.get("name_en", ""),
                    "name_zh": s.get("name_zh", ""),
                    "bgg_rating": s.get("bgg_rating", 0),
                    "bgg_weight": s.get("bgg_weight", 0),
                    "min_players": s.get("min_players", 0),
                    "max_players": s.get("max_players", 0),
                    "min_playtime": s.get("min_playtime", 0),
                    "max_playtime": s.get("max_playtime", 0),
                    "categories": [c["name"] for c in s.get("categories", [])],
                    "mechanics": [m["name"] for m in s.get("mechanics", [])],
                })

    if not games:
        has_filters = any(v is not None for k, v in intent.items() if k != "similar_to")
        if has_filters:
            games = await _context_search(
                intent["players"], intent["playtime"], intent["max_weight"],
                intent["category"], intent["mechanic"],
            )

    if not games:
        fq: dict = {}
        if intent["players"]:
            fq["min_players"] = {"$lte": intent["players"]}
            fq["max_players"] = {"$gte": intent["players"]}
        if not fq:
            games = await _search_games(msg.message)
        else:
            cursor = mongo_db.board_games.find(fq).sort("bgg_rating", -1).limit(8)
            async for doc in cursor:
                games.append({
                    "bgg_id": doc["bgg_id"],
                    "name_en": doc.get("name_en", ""),
                    "name_zh": doc.get("name_zh", ""),
                    "bgg_rating": doc.get("bgg_rating", 0),
                    "bgg_weight": doc.get("bgg_weight", 0),
                    "min_players": doc.get("min_players", 0),
                    "max_players": doc.get("max_players", 0),
                    "min_playtime": doc.get("min_playtime", 0),
                    "max_playtime": doc.get("max_playtime", 0),
                    "categories": [c["name"] for c in doc.get("categories", [])],
                    "mechanics": [m["name"] for m in doc.get("mechanics", [])],
                })

    if not games:
        games = await _search_games(msg.message)

    response_text = _format_games(games, msg.locale)

    return {
        "message": response_text,
        "games": games,
        "intent": intent,
    }
