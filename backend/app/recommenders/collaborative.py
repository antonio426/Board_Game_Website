import math
from collections import defaultdict

from app.core.database import mongo_db


class CollaborativeFilter:
    ACTION_WEIGHTS = {
        "view": 0.1,
        "click": 0.2,
        "wishlist": 0.8,
        "own": 0.9,
        "favorite": 1.0,
        "rate": 1.0,
    }

    def __init__(self):
        self._user_game_scores: dict[str, dict[int, float]] = {}
        self._game_user_scores: dict[int, dict[str, float]] = {}
        self._loaded = False

    async def _ensure_loaded(self):
        if self._loaded:
            return
        await self._build_interaction_matrix()
        self._loaded = True

    async def _build_interaction_matrix(self):
        cursor = mongo_db.user_actions.find(
            {},
            {"user_id": 1, "bgg_id": 1, "action_type": 1, "duration_sec": 1, "rating": 1},
        )

        user_game: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))

        async for doc in cursor:
            uid = doc["user_id"]
            gid = doc["bgg_id"]
            atype = doc.get("action_type", "view")
            weight = self.ACTION_WEIGHTS.get(atype, 0.1)

            score = weight
            if atype == "view":
                duration = doc.get("duration_sec", 0) or 0
                score = min(weight * (1 + duration / 120), 0.5)
            elif atype == "rate":
                rating = doc.get("rating") or 5
                score = weight * (rating / 10.0)

            user_game[uid][gid] += score

        self._user_game_scores = dict(user_game)

        game_user: dict[int, dict[str, float]] = defaultdict(dict)
        for uid, games in self._user_game_scores.items():
            for gid, score in games.items():
                game_user[gid][uid] = score

        self._game_user_scores = dict(game_user)

    def _cosine_similarity(self, a: dict, b: dict) -> float:
        common_keys = set(a.keys()) & set(b.keys())
        if not common_keys:
            return 0.0
        dot = sum(a[k] * b[k] for k in common_keys)
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def get_similar_games(self, bgg_id: int, top_k: int = 10) -> list[dict]:
        await self._ensure_loaded()

        target_users = self._game_user_scores.get(bgg_id)
        if not target_users:
            return []

        scores = []
        for other_id, other_users in self._game_user_scores.items():
            if other_id == bgg_id:
                continue
            sim = self._cosine_similarity(target_users, other_users)
            if sim > 0:
                scores.append({"bgg_id": other_id, "score": round(sim, 4)})

        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]

    async def recommend_for_user(self, user_id: str, top_k: int = 10) -> list[dict]:
        await self._ensure_loaded()

        user_scores = self._user_game_scores.get(user_id)
        if not user_scores:
            return []

        candidate_scores: dict[int, float] = defaultdict(float)

        for gid, user_score in user_scores.items():
            game_users = self._game_user_scores.get(gid, {})
            for other_id, other_users in self._game_user_scores.items():
                if other_id in user_scores:
                    continue
                sim = self._cosine_similarity(game_users, self._game_user_scores.get(other_id, {}))
                if sim > 0:
                    candidate_scores[other_id] += user_score * sim

        ranked = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
        return [{"bgg_id": gid, "score": round(score, 4)} for gid, score in ranked[:top_k]]

    async def get_similar_games_with_data(self, bgg_id: int, top_k: int = 10) -> list[dict]:
        similar = await self.get_similar_games(bgg_id, top_k)
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
