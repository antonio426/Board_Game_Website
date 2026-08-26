from app.recommenders.content_based import ContentBasedRecommender
from app.recommenders.collaborative import CollaborativeFilter
from app.core.database import mongo_db


class HybridRecommender:
    def __init__(self):
        self.cb = ContentBasedRecommender()
        self.cf = CollaborativeFilter()

    async def get_similar(self, bgg_id: int, top_k: int = 10, alpha: float = 0.6) -> list[dict]:
        cb_results = await self.cb.get_similar(bgg_id, top_k=top_k * 3)
        cf_results = await self.cf.get_similar_games(bgg_id, top_k=top_k * 3)

        cb_map = {r["bgg_id"]: r["score"] for r in cb_results}
        cf_map = {r["bgg_id"]: r["score"] for r in cf_results}

        all_ids = set(cb_map.keys()) | set(cf_map.keys())

        max_cb = max(cb_map.values()) if cb_map else 1.0
        max_cf = max(cf_map.values()) if cf_map else 1.0

        has_cf = bool(cf_map)
        effective_alpha = alpha if has_cf else 1.0

        combined = []
        for gid in all_ids:
            cb_score = (cb_map.get(gid, 0) / max_cb) if max_cb > 0 else 0
            cf_score = (cf_map.get(gid, 0) / max_cf) if max_cf > 0 else 0
            final = effective_alpha * cb_score + (1 - effective_alpha) * cf_score
            combined.append({"bgg_id": gid, "score": round(final, 4)})

        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[:top_k]

    async def get_similar_with_data(self, bgg_id: int, top_k: int = 10, alpha: float = 0.6) -> list[dict]:
        similar = await self.get_similar(bgg_id, top_k, alpha)
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

    async def recommend_for_user(
        self,
        user_id: str,
        top_k: int = 10,
        min_players: int | None = None,
        max_players: int | None = None,
        max_playtime: int | None = None,
    ) -> list[dict]:
        cf_results = await self.cf.recommend_for_user(user_id, top_k=top_k * 2)

        if not cf_results:
            user_prefs = await self._get_user_preferences(user_id)
            return await self.cb.recommend_for_preferences(
                liked_categories=user_prefs.get("categories"),
                liked_mechanics=user_prefs.get("mechanics"),
                preferred_weight=user_prefs.get("weight"),
                preferred_players=min_players or user_prefs.get("players"),
                top_k=top_k,
            )

        filter_query: dict = {}
        if min_players is not None:
            filter_query["min_players"] = {"$lte": min_players}
        if max_players is not None:
            filter_query["max_players"] = {"$gte": max_players}
        if max_playtime is not None:
            filter_query["min_playtime"] = {"$lte": max_playtime}

        ids = [r["bgg_id"] for r in cf_results]
        score_map = {r["bgg_id"]: r["score"] for r in cf_results}

        if filter_query:
            filter_query["bgg_id"] = {"$in": ids}
            cursor = mongo_db.board_games.find(filter_query)
        else:
            cursor = mongo_db.board_games.find({"bgg_id": {"$in": ids}})

        games = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            doc["recommendation_score"] = score_map.get(doc["bgg_id"], 0)
            games.append(doc)

        games.sort(key=lambda x: x.get("recommendation_score", 0), reverse=True)
        return games[:top_k]

    async def _get_user_preferences(self, user_id: str) -> dict:
        pipeline = [
            {"$match": {"user_id": user_id, "action_type": {"$in": ["rate", "wishlist", "favorite", "own"]}}},
            {"$lookup": {"from": "board_games", "localField": "bgg_id", "foreignField": "bgg_id", "as": "game"}},
            {"$unwind": "$game"},
            {"$group": {
                "_id": None,
                "categories": {"$push": "$game.categories"},
                "mechanics": {"$push": "$game.mechanics"},
                "weights": {"$push": "$game.bgg_weight"},
            }},
        ]

        result = await mongo_db.user_actions.aggregate(pipeline).to_list(length=1)
        if not result:
            return {}

        data = result[0]
        cat_counts: dict[str, int] = {}
        for cats in data.get("categories", []):
            for c in cats:
                cat_counts[c["name"]] = cat_counts.get(c["name"], 0) + 1

        mech_counts: dict[str, int] = {}
        for mechs in data.get("mechanics", []):
            for m in mechs:
                mech_counts[m["name"]] = mech_counts.get(m["name"], 0) + 1

        top_cats = sorted(cat_counts, key=cat_counts.get, reverse=True)[:5]
        top_mechs = sorted(mech_counts, key=mech_counts.get, reverse=True)[:5]
        avg_weight = sum(w for w in data.get("weights", []) if w) / max(len([w for w in data.get("weights", []) if w]), 1)

        return {"categories": top_cats, "mechanics": top_mechs, "weight": avg_weight, "players": None}
