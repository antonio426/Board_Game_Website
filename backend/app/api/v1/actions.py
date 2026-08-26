from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends

from app.core.database import mongo_db
from app.core.security import decode_access_token
from app.models.action import UserActionCreate, ActionType

router = APIRouter(prefix="/actions", tags=["actions"])


def _get_user_id(request: Request) -> str | None:
    token = request.cookies.get("token")
    if not token:
        return None
    payload = decode_access_token(token)
    return payload.get("sub") if payload else None


@router.post("")
async def record_action(action: UserActionCreate, request: Request):
    user_id = _get_user_id(request)
    doc = {
        "user_id": user_id or "anonymous",
        "bgg_id": action.bgg_id,
        "action_type": action.action_type.value,
        "duration_sec": action.duration_sec,
        "rating": action.rating,
        "search_query": action.search_query,
        "metadata": action.metadata,
        "created_at": datetime.now(timezone.utc),
    }
    await mongo_db.user_actions.insert_one(doc)
    return {"status": "ok"}


@router.get("/me")
async def get_my_actions(request: Request, limit: int = 100):
    user_id = _get_user_id(request)
    if not user_id:
        return {"actions": []}
    cursor = mongo_db.user_actions.find(
        {"user_id": user_id}
    ).sort("created_at", -1).limit(limit)
    actions = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        actions.append(doc)
    return {"actions": actions}


@router.get("/game/{bgg_id}")
async def get_game_actions(bgg_id: int, limit: int = 50):
    cursor = mongo_db.user_actions.find(
        {"bgg_id": bgg_id, "action_type": {"$in": ["rate", "wishlist", "favorite", "own"]}}
    ).sort("created_at", -1).limit(limit)
    actions = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        actions.append(doc)
    return {"actions": actions}


@router.post("/batch")
async def record_batch(actions: list[UserActionCreate], request: Request):
    user_id = _get_user_id(request)
    docs = []
    for action in actions:
        docs.append({
            "user_id": user_id or "anonymous",
            "bgg_id": action.bgg_id,
            "action_type": action.action_type.value,
            "duration_sec": action.duration_sec,
            "rating": action.rating,
            "search_query": action.search_query,
            "metadata": action.metadata,
            "created_at": datetime.now(timezone.utc),
        })
    if docs:
        await mongo_db.user_actions.insert_many(docs)
    return {"status": "ok", "count": len(docs)}


@router.get("/collection/me")
async def get_my_collection(request: Request, limit: int = 100):
    user_id = _get_user_id(request)
    if not user_id:
        return {"items": []}

    pipeline = [
        {"$match": {"user_id": user_id, "action_type": {"$in": ["wishlist", "own", "favorite", "rate"]}}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$bgg_id",
            "bgg_id": {"$first": "$bgg_id"},
            "action_type": {"$first": "$action_type"},
            "rating": {"$max": "$rating"},
            "created_at": {"$first": "$created_at"},
        }},
        {"$sort": {"created_at": -1}},
        {"$limit": limit},
    ]
    items = await mongo_db.user_actions.aggregate(pipeline).to_list(length=limit)

    bgg_ids = [it["bgg_id"] for it in items]
    games_cursor = mongo_db.board_games.find({"bgg_id": {"$in": bgg_ids}})
    games_map: dict[int, dict] = {}
    async for doc in games_cursor:
        doc["id"] = str(doc.pop("_id"))
        games_map[doc["bgg_id"]] = doc

    result = []
    for it in items:
        game = games_map.get(it["bgg_id"], {})
        result.append({
            "bgg_id": it["bgg_id"],
            "action_type": it["action_type"],
            "rating": it.get("rating"),
            "added_at": it["created_at"].isoformat() if it.get("created_at") else None,
            "game": game,
        })

    return {"items": result}


@router.delete("/{action_id}")
async def delete_action(action_id: str, request: Request):
    from bson import ObjectId
    user_id = _get_user_id(request)
    if not user_id:
        return {"status": "error", "message": "not authenticated"}

    result = await mongo_db.user_actions.delete_one({"_id": ObjectId(action_id), "user_id": user_id})
    return {"status": "ok", "deleted": result.deleted_count}


@router.post("/toggle")
async def toggle_action(action: UserActionCreate, request: Request):
    user_id = _get_user_id(request)
    if not user_id:
        return {"status": "error", "message": "not authenticated"}

    existing = await mongo_db.user_actions.find_one({
        "user_id": user_id,
        "bgg_id": action.bgg_id,
        "action_type": action.action_type.value,
    })

    if existing:
        await mongo_db.user_actions.delete_one({"_id": existing["_id"]})
        return {"status": "removed", "action_id": str(existing["_id"])}
    else:
        doc = {
            "user_id": user_id,
            "bgg_id": action.bgg_id,
            "action_type": action.action_type.value,
            "duration_sec": action.duration_sec,
            "rating": action.rating,
            "search_query": action.search_query,
            "metadata": action.metadata,
            "created_at": datetime.now(timezone.utc),
        }
        result = await mongo_db.user_actions.insert_one(doc)
        return {"status": "added", "action_id": str(result.inserted_id)}
