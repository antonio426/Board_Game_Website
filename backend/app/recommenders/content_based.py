import math
from collections import defaultdict

from app.core.database import mongo_db


class ContentBasedRecommender:
    def __init__(self):
        self._game_features: dict[int, dict] = {}
        self._category_index: dict[str, int] = {}
        self._mechanic_index: dict[str, int] = {}
        self._loaded = False

    async def _ensure_loaded(self):
        if self._loaded:
            return
        await self._build_feature_index()
        self._loaded = True

    async def _build_feature_index(self):
        cat_set: set[str] = set()
        mech_set: set[str] = set()

        cursor = mongo_db.board_games.find(
            {},
            {"bgg_id": 1, "categories": 1, "mechanics": 1, "bgg_weight": 1,
             "min_players": 1, "max_players": 1, "min_playtime": 1, "max_playtime": 1},
        )

        games_raw: dict[int, dict] = {}
        async for doc in cursor:
            bgg_id = doc["bgg_id"]
            games_raw[bgg_id] = doc
            for c in doc.get("categories", []):
                cat_set.add(c["name"])
            for m in doc.get("mechanics", []):
                mech_set.add(m["name"])

        sorted_cats = sorted(cat_set)
        sorted_mechs = sorted(mech_set)
        self._category_index = {c: i for i, c in enumerate(sorted_cats)}
        self._mechanic_index = {m: i for i, m in enumerate(sorted_mechs)}

        cat_dim = len(self._category_index)
        mech_dim = len(self._mechanic_index)

        for bgg_id, doc in games_raw.items():
            feature = [0.0] * (cat_dim + mech_dim + 4)

            for c in doc.get("categories", []):
                idx = self._category_index.get(c["name"])
                if idx is not None:
                    feature[idx] = 1.0

            for m in doc.get("mechanics", []):
                idx = self._mechanic_index.get(m["name"])
                if idx is not None:
                    feature[cat_dim + idx] = 1.0

            weight = doc.get("bgg_weight", 0) or 0
            feature[cat_dim + mech_dim] = min(weight / 5.0, 1.0)

            avg_players = ((doc.get("min_players", 0) or 0) + (doc.get("max_players", 0) or 0)) / 2
            feature[cat_dim + mech_dim + 1] = min(avg_players / 10.0, 1.0)

            avg_playtime = ((doc.get("min_playtime", 0) or 0) + (doc.get("max_playtime", 0) or 0)) / 2
            feature[cat_dim + mech_dim + 2] = min(avg_playtime / 240.0, 1.0)

            feature[cat_dim + mech_dim + 3] = 1.0

            self._game_features[bgg_id] = {"feature": feature, "raw": doc}

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def get_similar(self, bgg_id: int, top_k: int = 10) -> list[dict]:
        await self._ensure_loaded()

        target = self._game_features.get(bgg_id)
        if not target:
            return []

        target_vec = target["feature"]
        scores = []

        for other_id, other_data in self._game_features.items():
            if other_id == bgg_id:
                continue
            sim = self._cosine_similarity(target_vec, other_data["feature"])
            scores.append({"bgg_id": other_id, "score": round(sim, 4)})

        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]

    async def get_similar_games_with_data(self, bgg_id: int, top_k: int = 10) -> list[dict]:
        similar = await self.get_similar(bgg_id, top_k)
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

    async def recommend_for_preferences(
        self,
        liked_categories: list[str] | None = None,
        liked_mechanics: list[str] | None = None,
        preferred_weight: float | None = None,
        preferred_players: int | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        await self._ensure_loaded()

        if not self._category_index and not self._mechanic_index:
            return []

        cat_dim = len(self._category_index)
        mech_dim = len(self._mechanic_index)
        query_vec = [0.0] * (cat_dim + mech_dim + 4)

        if liked_categories:
            for c in liked_categories:
                idx = self._category_index.get(c)
                if idx is not None:
                    query_vec[idx] = 1.0

        if liked_mechanics:
            for m in liked_mechanics:
                idx = self._mechanic_index.get(m)
                if idx is not None:
                    query_vec[cat_dim + idx] = 1.0

        if preferred_weight is not None:
            query_vec[cat_dim + mech_dim] = min(preferred_weight / 5.0, 1.0)

        if preferred_players is not None:
            query_vec[cat_dim + mech_dim + 1] = min(preferred_players / 10.0, 1.0)

        scores = []
        for bgg_id, data in self._game_features.items():
            sim = self._cosine_similarity(query_vec, data["feature"])
            scores.append({"bgg_id": bgg_id, "score": round(sim, 4)})

        scores.sort(key=lambda x: x["score"], reverse=True)
        top = scores[:top_k]

        if not top:
            return []

        ids = [s["bgg_id"] for s in top]
        score_map = {s["bgg_id"]: s["score"] for s in top}

        games = []
        cursor = mongo_db.board_games.find({"bgg_id": {"$in": ids}})
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            doc["recommendation_score"] = score_map.get(doc["bgg_id"], 0)
            games.append(doc)

        games.sort(key=lambda x: x.get("recommendation_score", 0), reverse=True)
        return games
