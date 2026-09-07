"""Content-based similarity over categories, mechanics, weight and length.

The previous implementation built a dense one-hot vector per game — 281 tag
dimensions plus four numeric ones — for all 180k documents, including the 137k
stub rows that never appear in results, and compared the query against every
one of them. This version keeps tags as sets and only loads games that can
actually be recommended, which makes the comparison both faster and explainable:
the overlap it scores with is exactly what the UI shows as "why this one".
"""
import math

from app.core.database import mongo_db
from app.core.filters import BASE_GAMES_ONLY
from app.core.quality import merge_filters, QUALITY_FILTER

# How much of the similarity each signal is worth.
TAG_WEIGHT = 0.75
WEIGHT_WEIGHT = 0.15
LENGTH_WEIGHT = 0.10

# Complexity and playtime distances are normalised against these spans.
WEIGHT_SPAN = 4.0        # bgg_weight runs 1-5
PLAYTIME_SPAN = 180.0    # minutes; beyond this, games are simply "long"

CORPUS_FILTER = merge_filters(QUALITY_FILTER, BASE_GAMES_ONLY, {"users_rated": {"$gte": 30}})
PROJECTION = {
    "bgg_id": 1, "categories": 1, "mechanics": 1, "bgg_weight": 1,
    "min_players": 1, "max_players": 1, "min_playtime": 1, "max_playtime": 1,
    "quality_score": 1, "series": 1,
}


def _names(doc: dict, field: str) -> frozenset[str]:
    values = set()
    for item in doc.get(field) or []:
        name = item.get("name") if isinstance(item, dict) else item
        if name:
            values.add(name)
    return frozenset(values)


def _playtime(doc: dict) -> float:
    low = doc.get("min_playtime") or 0
    high = doc.get("max_playtime") or low
    return (low + high) / 2 if (low or high) else 0.0


class ContentBasedRecommender:
    def __init__(self):
        self._features: dict[int, dict] = {}
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        cursor = mongo_db.board_games.find(CORPUS_FILTER, PROJECTION)
        async for doc in cursor:
            self._features[doc["bgg_id"]] = {
                "categories": _names(doc, "categories"),
                "mechanics": _names(doc, "mechanics"),
                "weight": doc.get("bgg_weight") or 0.0,
                "playtime": _playtime(doc),
                "quality": doc.get("quality_score") or 0.0,
            }
        self._loaded = True

    @staticmethod
    def _tag_similarity(left: frozenset[str], right: frozenset[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / math.sqrt(len(left) * len(right))

    @staticmethod
    def _numeric_similarity(left: float, right: float, span: float) -> float:
        if not left or not right:
            return 0.0
        return max(0.0, 1.0 - abs(left - right) / span)

    def _score(self, target: dict, other: dict) -> float:
        tags = (
            self._tag_similarity(target["categories"], other["categories"])
            + self._tag_similarity(target["mechanics"], other["mechanics"])
        ) / 2
        return (
            TAG_WEIGHT * tags
            + WEIGHT_WEIGHT * self._numeric_similarity(target["weight"], other["weight"], WEIGHT_SPAN)
            + LENGTH_WEIGHT * self._numeric_similarity(target["playtime"], other["playtime"], PLAYTIME_SPAN)
        )

    @staticmethod
    def _overlap(target: dict, other: dict) -> dict:
        return {
            "matched_categories": sorted(target["categories"] & other["categories"]),
            "matched_mechanics": sorted(target["mechanics"] & other["mechanics"]),
        }

    async def get_similar(self, bgg_id: int, top_k: int = 10) -> list[dict]:
        await self._ensure_loaded()
        target = self._features.get(bgg_id)
        if not target:
            return []

        scored = []
        for other_id, other in self._features.items():
            if other_id == bgg_id:
                continue
            score = self._score(target, other)
            if score <= 0:
                continue
            scored.append({
                "bgg_id": other_id,
                "score": round(score, 4),
                "reasoning": self._overlap(target, other),
            })

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    async def get_similar_games_with_data(self, bgg_id: int, top_k: int = 10) -> list[dict]:
        return await attach_games(await self.get_similar(bgg_id, top_k))

    async def recommend_for_preferences(
        self,
        liked_categories: list[str] | None = None,
        liked_mechanics: list[str] | None = None,
        preferred_weight: float | None = None,
        preferred_playtime: float | None = None,
        exclude_ids: set[int] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """Rank the corpus against a taste profile rather than another game."""
        await self._ensure_loaded()

        target = {
            "categories": frozenset(liked_categories or []),
            "mechanics": frozenset(liked_mechanics or []),
            "weight": preferred_weight or 0.0,
            "playtime": preferred_playtime or 0.0,
        }
        if not (target["categories"] or target["mechanics"] or target["weight"]):
            return []

        excluded = exclude_ids or set()
        scored = []
        for bgg_id, other in self._features.items():
            if bgg_id in excluded:
                continue
            score = self._score(target, other)
            if score <= 0:
                continue
            scored.append({
                "bgg_id": bgg_id,
                # A tie on taste is broken by how well the game is regarded.
                "score": round(score + other["quality"] / 100, 4),
                "reasoning": self._overlap(target, other),
            })

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]


async def attach_games(scored: list[dict]) -> list[dict]:
    """Hydrate scored `bgg_id`s into full documents, preserving order."""
    if not scored:
        return []

    by_id = {item["bgg_id"]: item for item in scored}
    games = []
    async for doc in mongo_db.board_games.find({"bgg_id": {"$in": list(by_id)}}):
        item = by_id[doc["bgg_id"]]
        doc["id"] = str(doc.pop("_id"))
        doc["recommendation_score"] = item["score"]
        if item.get("reasoning"):
            doc["reasoning"] = item["reasoning"]
        games.append(doc)

    games.sort(key=lambda doc: doc.get("recommendation_score", 0), reverse=True)
    return games
