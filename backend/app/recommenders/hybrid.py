"""Blends content similarity with collaborative signal, degrading as data allows.

The collaborative filter is built from `user_actions`, of which there are 15
across 0 registered users, so in practice it contributes nothing today. Rather
than pretend otherwise, the blend weights itself by what actually came back and
the fallback chain is explicit:

    collaborative (needs interactions) -> content similarity -> taste profile
    -> quality_score leaderboard
"""
from app.core.database import mongo_db
from app.core.filters import BASE_GAMES_ONLY
from app.core.quality import merge_filters, QUALITY_FILTER
from app.recommenders.collaborative import CollaborativeFilter
from app.recommenders.content_based import ContentBasedRecommender, attach_games

CONTENT_WEIGHT = 0.6
MIN_ACTIONS_FOR_COLLABORATIVE = 5


class HybridRecommender:
    def __init__(self):
        self.cb = ContentBasedRecommender()
        self.cf = CollaborativeFilter()

    async def get_similar(self, bgg_id: int, top_k: int = 10, alpha: float = CONTENT_WEIGHT) -> list[dict]:
        content = await self.cb.get_similar(bgg_id, top_k=top_k * 3)
        collaborative = await self.cf.get_similar_games(bgg_id, top_k=top_k * 3)

        content_map = {item["bgg_id"]: item for item in content}
        collaborative_map = {item["bgg_id"]: item["score"] for item in collaborative}

        highest_content = max((item["score"] for item in content), default=1.0) or 1.0
        highest_collaborative = max(collaborative_map.values(), default=1.0) or 1.0

        # With no collaborative signal the blend is pure content similarity,
        # rather than a 0.6 weighting of something and 0.4 of nothing.
        weight = alpha if collaborative_map else 1.0

        combined = []
        for game_id in set(content_map) | set(collaborative_map):
            content_score = (content_map.get(game_id, {}).get("score", 0)) / highest_content
            collaborative_score = collaborative_map.get(game_id, 0) / highest_collaborative
            combined.append({
                "bgg_id": game_id,
                "score": round(weight * content_score + (1 - weight) * collaborative_score, 4),
                "reasoning": content_map.get(game_id, {}).get("reasoning"),
            })

        combined.sort(key=lambda item: item["score"], reverse=True)
        return combined[:top_k]

    async def get_similar_with_data(self, bgg_id: int, top_k: int = 10, alpha: float = CONTENT_WEIGHT) -> list[dict]:
        return await attach_games(await self.get_similar(bgg_id, top_k, alpha))

    async def recommend_for_user(
        self,
        user_id: str,
        top_k: int = 10,
        min_players: int | None = None,
        max_players: int | None = None,
        max_playtime: int | None = None,
    ) -> list[dict]:
        """Best available personalisation for this user, in order of evidence."""
        interactions = await mongo_db.user_actions.count_documents({"user_id": user_id})

        if interactions >= MIN_ACTIONS_FOR_COLLABORATIVE:
            collaborative = await self.cf.recommend_for_user(user_id, top_k=top_k * 2)
            if collaborative:
                games = await attach_games(collaborative)
                games = _apply_constraints(games, min_players, max_players, max_playtime)
                if games:
                    return games[:top_k]

        preferences = await self.taste_profile(user_id)
        if preferences.get("categories") or preferences.get("mechanics"):
            scored = await self.cb.recommend_for_preferences(
                liked_categories=preferences.get("categories"),
                liked_mechanics=preferences.get("mechanics"),
                preferred_weight=preferences.get("weight"),
                exclude_ids=preferences.get("seen_ids"),
                top_k=top_k * 2,
            )
            games = _apply_constraints(await attach_games(scored), min_players, max_players, max_playtime)
            if games:
                return games[:top_k]

        return await popular_games(top_k)

    async def taste_profile(self, user_id: str) -> dict:
        """Categories, mechanics and complexity the user keeps coming back to."""
        pipeline = [
            {"$match": {"user_id": user_id, "action_type": {"$in": ["rate", "wishlist", "favorite", "own"]}}},
            {"$lookup": {"from": "board_games", "localField": "bgg_id",
                         "foreignField": "bgg_id", "as": "game"}},
            {"$unwind": "$game"},
        ]

        category_counts: dict[str, int] = {}
        mechanic_counts: dict[str, int] = {}
        weights: list[float] = []
        seen_ids: set[int] = set()

        async for row in mongo_db.user_actions.aggregate(pipeline):
            game = row["game"]
            seen_ids.add(game.get("bgg_id"))
            for item in game.get("categories") or []:
                name = item.get("name") if isinstance(item, dict) else item
                if name:
                    category_counts[name] = category_counts.get(name, 0) + 1
            for item in game.get("mechanics") or []:
                name = item.get("name") if isinstance(item, dict) else item
                if name:
                    mechanic_counts[name] = mechanic_counts.get(name, 0) + 1
            if game.get("bgg_weight"):
                weights.append(game["bgg_weight"])

        return {
            "categories": sorted(category_counts, key=category_counts.get, reverse=True)[:5],
            "mechanics": sorted(mechanic_counts, key=mechanic_counts.get, reverse=True)[:5],
            "weight": sum(weights) / len(weights) if weights else None,
            "seen_ids": seen_ids,
        }


def _apply_constraints(games: list[dict], min_players, max_players, max_playtime) -> list[dict]:
    def fits(game: dict) -> bool:
        if min_players is not None and (game.get("min_players") or 0) > min_players:
            return False
        if max_players is not None and (game.get("max_players") or 0) < max_players:
            return False
        if max_playtime is not None and (game.get("min_playtime") or 0) > max_playtime:
            return False
        return True

    return [game for game in games if fits(game)]


async def popular_games(top_k: int = 10) -> list[dict]:
    """Last resort: the games most people agree are good."""
    query = merge_filters(QUALITY_FILTER, BASE_GAMES_ONLY, {"users_rated": {"$gte": 1000}})
    cursor = mongo_db.board_games.find(query).sort("quality_score", -1).limit(top_k)

    games = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        doc["recommendation_score"] = doc.get("quality_score", 0)
        games.append(doc)
    return games
