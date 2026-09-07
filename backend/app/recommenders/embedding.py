"""Vector search over board games, backed by a real sentence embedding model.

Until Phase 1 this module hashed the text with SHA-256 and spread the bytes
through `sin()`, which produced 384 well-formed numbers with no semantic
content whatsoever — "deck building card game" retrieved "Vanished Planet:
Racial Advantage Expansion".

It now uses fastembed with `BAAI/bge-small-en-v1.5`, a retrieval-trained model
at the same 384 dimensions the collection already uses. A multilingual
paraphrase model was tried first and retrieved worse: paraphrase models score
"is this the same sentence", not "does this passage answer this question", so
"birds engine builder" came back as five games with Birds in the title and no
Wingspan. Chinese queries are served by the lexical path instead, which matches
name_zh and aliases directly — and with Chinese descriptions on 14 of 43,401
games there is nothing for a multilingual model to retrieve anyway.
"""
import logging
from threading import Lock

from qdrant_client.models import Distance, FieldCondition, Filter, MatchAny, PointStruct, Range, VectorParams

from app.core.config import settings
from app.core.database import qdrant_client, mongo_db
from app.core.quality import QUALITY_FILTER

logger = logging.getLogger(__name__)

COLLECTION = "board_games"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384
DESCRIPTION_CHARS = 400

_model = None
_model_lock = Lock()
_model_failed = False


def _get_model():
    """Load the embedding model once, lazily — it costs ~220 MB of downloads."""
    global _model, _model_failed
    if _model is not None or _model_failed:
        return _model
    with _model_lock:
        if _model is None and not _model_failed:
            try:
                from fastembed import TextEmbedding

                _model = TextEmbedding(model_name=MODEL_NAME)
                logger.info("embedding model loaded: %s", MODEL_NAME)
            except Exception as exc:
                _model_failed = True
                logger.error("embedding model unavailable, semantic search disabled: %s", exc)
    return _model


def semantic_enabled() -> bool:
    """Whether vector results are trustworthy enough to show."""
    if not settings.SEMANTIC_SEARCH_ENABLED:
        return False
    return _get_model() is not None


def embed(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    if model is None:
        return []
    return [vector.tolist() for vector in model.embed(texts)]


def embed_query(text: str) -> list[float] | None:
    """Queries get the model's query-side treatment; passages do not."""
    model = _get_model()
    if model is None:
        return None
    return next(iter(model.query_embed([text]))).tolist()


def _ensure_collection() -> None:
    names = [c.name for c in qdrant_client.get_collections().collections]
    if COLLECTION not in names:
        qdrant_client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def _tag_names(doc: dict, field: str) -> list[str]:
    names = []
    for item in doc.get(field) or []:
        name = item.get("name") if isinstance(item, dict) else item
        if name:
            names.append(name)
    return names


def game_text(doc: dict) -> str:
    """What the model sees.

    Tags come before the description because they are the part a query like
    "co-op deck builder for two" actually refers to, and marketing copy dilutes
    the average once it runs long.
    """
    categories = ", ".join(_tag_names(doc, "categories"))
    mechanics = ", ".join(_tag_names(doc, "mechanics"))
    parts = [
        doc.get("name_en") or doc.get("name_zh") or "",
        f"Categories: {categories}" if categories else "",
        f"Mechanics: {mechanics}" if mechanics else "",
        (doc.get("description_en") or "")[:DESCRIPTION_CHARS],
    ]
    return ". ".join(part for part in parts if part).strip()


async def index_games(batch_size: int = 256, limit: int | None = None) -> int:
    """(Re)build vectors for every showable game. Safe to re-run."""
    _ensure_collection()
    if _get_model() is None:
        raise RuntimeError(f"embedding model {MODEL_NAME} unavailable")

    projection = {
        "bgg_id": 1, "name_en": 1, "name_zh": 1, "categories": 1,
        "mechanics": 1, "description_en": 1, "users_rated": 1,
    }
    cursor = mongo_db.board_games.find(QUALITY_FILTER, projection).sort("users_rated", -1)
    if limit:
        cursor = cursor.limit(limit)

    indexed = 0
    batch: list[dict] = []

    async def flush(docs: list[dict]) -> int:
        vectors = embed([game_text(doc) for doc in docs])
        points = [
            PointStruct(
                id=doc["bgg_id"],
                vector=vector,
                payload={
                    "bgg_id": doc["bgg_id"],
                    "name_en": doc.get("name_en") or "",
                    "name_zh": doc.get("name_zh") or "",
                    "categories": _tag_names(doc, "categories"),
                    "mechanics": _tag_names(doc, "mechanics"),
                    "users_rated": doc.get("users_rated") or 0,
                },
            )
            for doc, vector in zip(docs, vectors)
        ]
        qdrant_client.upsert(collection_name=COLLECTION, points=points)
        return len(points)

    async for doc in cursor:
        batch.append(doc)
        if len(batch) >= batch_size:
            indexed += await flush(batch)
            batch = []

    if batch:
        indexed += await flush(batch)

    return indexed


def _build_filter(categories: list[str] | None, mechanics: list[str] | None, min_users_rated: int) -> Filter | None:
    conditions = []
    if categories:
        conditions.append(FieldCondition(key="categories", match=MatchAny(any=categories)))
    if mechanics:
        conditions.append(FieldCondition(key="mechanics", match=MatchAny(any=mechanics)))
    if min_users_rated:
        conditions.append(FieldCondition(key="users_rated", range=Range(gte=min_users_rated)))
    return Filter(must=conditions) if conditions else None


async def search_similar(
    query: str,
    top_k: int = 10,
    categories: list[str] | None = None,
    mechanics: list[str] | None = None,
    min_users_rated: int = 0,
) -> list[dict]:
    """Vector search, optionally narrowed by tags before scoring."""
    _ensure_collection()
    vector = embed_query(query)
    if vector is None:
        return []

    results = qdrant_client.query_points(
        collection_name=COLLECTION,
        query=vector,
        limit=top_k,
        query_filter=_build_filter(categories, mechanics, min_users_rated),
    )
    return [
        {"bgg_id": point.payload["bgg_id"], "score": round(point.score, 4)}
        for point in results.points
        if point.payload
    ]


async def search_similar_with_data(query: str, top_k: int = 10, **kwargs) -> list[dict]:
    similar = await search_similar(query, top_k, **kwargs)
    if not similar:
        return []

    score_map = {item["bgg_id"]: item["score"] for item in similar}
    games = []
    async for doc in mongo_db.board_games.find({"bgg_id": {"$in": list(score_map)}}):
        doc["id"] = str(doc.pop("_id"))
        doc["recommendation_score"] = score_map.get(doc["bgg_id"], 0)
        games.append(doc)

    games.sort(key=lambda game: game.get("recommendation_score", 0), reverse=True)
    return games
