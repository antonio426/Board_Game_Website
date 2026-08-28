import hashlib
import math
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.core.database import qdrant_client, mongo_db

COLLECTION = "board_games"
VECTOR_SIZE = 384


def _ensure_collection():
    collections = qdrant_client.get_collections()
    names = [c.name for c in collections.collections]
    if COLLECTION not in names:
        qdrant_client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def _text_to_vector(text: str) -> list[float]:
    h = hashlib.sha256(text.encode()).digest()
    vec = []
    for i in range(VECTOR_SIZE):
        byte_idx = (i * 4) % len(h)
        chunk = h[byte_idx:byte_idx + 4]
        if len(chunk) < 4:
            chunk = chunk + h[:4 - len(chunk)]
        val = int.from_bytes(chunk, "little")
        vec.append(math.sin(val) * 0.5)
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


async def index_games(batch_size: int = 100):
    _ensure_collection()

    total = await mongo_db.board_games.count_documents({})
    indexed = 0

    cursor = mongo_db.board_games.find(
        {},
        {"bgg_id": 1, "name_en": 1, "name_zh": 1, "categories": 1, "mechanics": 1, "description_en": 1},
    )

    points = []
    async for doc in cursor:
        text_parts = [
            doc.get("name_en", ""),
            doc.get("name_zh", ""),
            " ".join(c["name"] if isinstance(c, dict) else c for c in doc.get("categories", [])),
            " ".join(m["name"] if isinstance(m, dict) else m for m in doc.get("mechanics", [])),
            (doc.get("description_en", "") or "")[:200],
        ]
        text = " ".join(p for p in text_parts if p).strip()
        vector = _text_to_vector(text)

        points.append(PointStruct(
            id=doc["bgg_id"],
            vector=vector,
            payload={"bgg_id": doc["bgg_id"], "name_en": doc.get("name_en", ""), "name_zh": doc.get("name_zh", "")},
        ))

        if len(points) >= batch_size:
            qdrant_client.upsert(collection_name=COLLECTION, points=points)
            indexed += len(points)
            points = []

    if points:
        qdrant_client.upsert(collection_name=COLLECTION, points=points)
        indexed += len(points)

    return indexed


async def search_similar(query: str, top_k: int = 10) -> list[dict]:
    _ensure_collection()
    vector = _text_to_vector(query)

    results = qdrant_client.query_points(
        collection_name=COLLECTION,
        query=vector,
        limit=top_k,
    )

    return [{"bgg_id": r.payload["bgg_id"], "score": round(r.score, 4)} for r in results.points]


async def search_similar_with_data(query: str, top_k: int = 10) -> list[dict]:
    similar = await search_similar(query, top_k)
    if not similar:
        return []

    ids = [s["bgg_id"] for s in similar]
    score_map = {s["bgg_id"]: s["score"] for s in similar}

    games = []
    cursor = mongo_db.board_games.find({"bgg_id": {"$in": ids}})
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        doc["recommendation_score"] = score_map.get(doc["bgg_id"], 0)
        games.append(doc)

    games.sort(key=lambda x: x.get("recommendation_score", 0), reverse=True)
    return games
