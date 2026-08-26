import asyncio
import csv
import io
from datetime import datetime, timezone

from app.core.database import mongo_db


async def import_bgg_csv(csv_path: str):
    subcategory_columns = {
        "abstracts_rank": "abstracts",
        "cgs_rank": "cgs",
        "childrensgames_rank": "childrens",
        "familygames_rank": "family",
        "partygames_rank": "party",
        "strategygames_rank": "strategy",
        "thematic_rank": "thematic",
        "wargames_rank": "wargames",
    }

    def _parse_int(value, default=0):
        try:
            return int(value) if value not in (None, "") else default
        except (ValueError, TypeError):
            return default

    def _parse_float(value, default=0.0):
        try:
            return float(value) if value not in (None, "") else default
        except (ValueError, TypeError):
            return default

    def _subcategory_ranks(row):
        ranks = {}
        for col, key in subcategory_columns.items():
            v = (row.get(col) or "").strip()
            if v:
                ranks[key] = _parse_int(v)
        return ranks

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = 0
        batch = []
        for row in reader:
            try:
                game = {
                    "bgg_id": _parse_int(row.get("id", 0) or row.get("BGGId", 0)),
                    "name_en": row.get("name", row.get("Name", "")),
                    "name_zh": row.get("name_zh", ""),
                    "description_en": row.get("description", ""),
                    "description_zh": "",
                    "thumbnail": row.get("thumbnail", ""),
                    "image": row.get("image", ""),
                    "local_thumbnail": "",
                    "local_image": "",
                    "year_published": _parse_int(row.get("yearpublished", 0)),
                    "min_players": _parse_int(row.get("minplayers", 0)),
                    "max_players": _parse_int(row.get("maxplayers", 0)),
                    "min_playtime": _parse_int(row.get("minplaytime", 0)),
                    "max_playtime": _parse_int(row.get("maxplaytime", 0)),
                    "min_age": _parse_int(row.get("minage", 0)),
                    "bgg_rating": _parse_float(row.get("bayesaverage", 0)),
                    "bgg_avg_rating": _parse_float(row.get("average", 0)),
                    "bgg_rank": _parse_int(row.get("rank", 99999), 99999),
                    "is_expansion": _parse_int(row.get("is_expansion", 0)),
                    "subcategory_ranks": _subcategory_ranks(row),
                    "bgg_weight": _parse_float(row.get("avg_weight", row.get("weight", 0))),
                    "users_rated": _parse_int(row.get("usersrated", row.get("num_voters", 0))),
                    "categories": _parse_tags(row.get("categories", "")),
                    "mechanics": _parse_tags(row.get("mechanics", "")),
                    "expansions": [],
                    "series": [],
                    "designers": _parse_list(row.get("designers", "")),
                    "publishers": _parse_list(row.get("publishers", "")),
                    "updated_at": datetime.now(timezone.utc),
                }
                batch.append(game)
                count += 1

                if len(batch) >= 50:
                    await _save_batch(batch)
                    batch = []
            except (ValueError, KeyError) as e:
                print(f"Skipping row: {e}")
                continue

        if batch:
            await _save_batch(batch)

        print(f"Import complete. {count} games saved.")


def _parse_tags(value: str) -> list[dict]:
    if not value:
        return []
    items = [t.strip() for t in value.replace("[", "").replace("]", "").replace("'", "").split(",") if t.strip()]
    return [{"id": i, "name": name} for i, name in enumerate(items)]


def _parse_list(value: str) -> list[str]:
    if not value:
        return []
    return [t.strip() for t in value.replace("[", "").replace("]", "").replace("'", "").split(",") if t.strip()]


async def _save_batch(games: list[dict]):
    for game in games:
        await mongo_db.board_games.update_one(
            {"bgg_id": game["bgg_id"]},
            {
                "$set": game,
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
            },
            upsert=True,
        )
    print(f"Saved batch of {len(games)} games")


async def import_sample_data():
    sample_games = [
        {
            "bgg_id": 174430, "name_en": "Gloomhaven", "name_zh": "幽暗港灣",
            "description_en": "Gloomhaven is a game of Euro-inspired tactical combat in a persistent world of shifting motives. Players take on the role of wandering mercenaries with their own special skills and reasons for traveling.",
            "description_zh": "幽暗港灣是一款歐式靈感的戰術戰鬥遊戲，在一個不斷變化的世界中，玩家扮演擁有特殊技能和旅行理由的流浪傭兵。",
            "image": "https://cf.geekdo-images.com/itemrep/img/PJo3YMiVP_i0EBkMJ5OqpBMLYDo=/fit-in/246x300/pic2437871.jpg",
            "thumbnail": "https://cf.geekdo-images.com/thumb/img/kajPQ7aJ8c7MMa8LtF2u9bd8Mp4=/fit-in/100x100/pic2437871.jpg",
            "bgg_rating": 8.65, "bgg_rank": 1, "bgg_weight": 3.86,
            "min_players": 1, "max_players": 4, "min_playtime": 60, "max_playtime": 120,
            "min_age": 14, "year_published": 2017, "users_rated": 43000,
            "categories": [{"id": 0, "name": "Thematic"}, {"id": 1, "name": "Adventure"}],
            "mechanics": [{"id": 0, "name": "Cooperative"}, {"id": 1, "name": "Action Points"}, {"id": 2, "name": "Card Drafting"}],
            "designers": ["Isaac Childres"], "publishers": ["Cephalofair Games"],
        },
        {
            "bgg_id": 224517, "name_en": "Brass: Birmingham", "name_zh": "黃銅：伯明翰",
            "description_en": "Brass: Birmingham tells the story of competing entrepreneurs in Birmingham during the English Industrial Revolution between 1770-1870.",
            "description_zh": "黃銅：伯明翰講述了1770至1870年間英國工業革命時期，伯明翰企業家之間競爭的故事。",
            "image": "https://cf.geekdo-images.com/itemrep/img/U4lP5LGAK4qN8QNP6w4rqz0VFCk=/fit-in/246x300/pic3786156.jpg",
            "thumbnail": "https://cf.geekdo-images.com/thumb/img/MFJNqFnVz9V-0Ej1WjDJCgE0JMI=/fit-in/100x100/pic3786156.jpg",
            "bgg_rating": 8.58, "bgg_rank": 2, "bgg_weight": 3.90,
            "min_players": 2, "max_players": 4, "min_playtime": 60, "max_playtime": 120,
            "min_age": 14, "year_published": 2018, "users_rated": 28000,
            "categories": [{"id": 0, "name": "Economic"}, {"id": 1, "name": "Industry"}],
            "mechanics": [{"id": 0, "name": "Hand Management"}, {"id": 1, "name": "Network Building"}],
            "designers": ["Martin Wallace"], "publishers": ["Roxley Games"],
        },
        {
            "bgg_id": 161936, "name_en": "Pandemic Legacy: Season 1", "name_zh": "瘟疫危機：傳承 第1季",
            "description_en": "Pandemic Legacy is a co-operative campaign game with an overarching story-arc. The choices you make in each game affect future games.",
            "description_zh": "瘟疫危機：傳承是一款合作戰役遊戲，具有整體故事線。你在每場遊戲中做出的選擇會影響未來的遊戲。",
            "image": "https://cf.geekdo-images.com/itemrep/img/3MGA17k5liGSboVwJm6FGqJ5Vag=/fit-in/246x300/pic2452833.jpg",
            "thumbnail": "https://cf.geekdo-images.com/thumb/img/br7IMkq-CX7MJdZNMIRy-LInF6E=/fit-in/100x100/pic2452833.jpg",
            "bgg_rating": 8.52, "bgg_rank": 3, "bgg_weight": 2.83,
            "min_players": 2, "max_players": 4, "min_playtime": 60, "max_playtime": 60,
            "min_age": 13, "year_published": 2015, "users_rated": 20000,
            "categories": [{"id": 0, "name": "Cooperative"}, {"id": 1, "name": "Medical"}],
            "mechanics": [{"id": 0, "name": "Cooperative"}, {"id": 1, "name": "Action Points"}],
            "designers": ["Matt Leacock", "Rob Daviau"], "publishers": ["Z-Man Games"],
        },
        {
            "bgg_id": 2651, "name_en": "Catan", "name_zh": "卡坦島",
            "description_en": "In Catan, players try to be the dominant force on the island of Catan by building settlements, cities, and roads.",
            "description_zh": "在卡坦島中，玩家通過建造村莊、城市和道路，試圖成為卡坦島上的主導力量。",
            "image": "https://cf.geekdo-images.com/itemrep/img/Wg4Jo5HEHxdVsIQPD89nNqy60EY=/fit-in/246x300/pic3917563.jpg",
            "thumbnail": "https://cf.geekdo-images.com/thumb/img/L4WciSMtM2c8RJJaBRk3yJPM7W4=/fit-in/100x100/pic3917563.jpg",
            "bgg_rating": 7.18, "bgg_rank": 500, "bgg_weight": 2.32,
            "min_players": 3, "max_players": 4, "min_playtime": 60, "max_playtime": 120,
            "min_age": 10, "year_published": 1995, "users_rated": 85000,
            "categories": [{"id": 0, "name": "Economic"}, {"id": 1, "name": "Negotiation"}],
            "mechanics": [{"id": 0, "name": "Dice Rolling"}, {"id": 1, "name": "Modular Board"}, {"id": 2, "name": "Trading"}],
            "designers": ["Klaus Teuber"], "publishers": ["Kosmos"],
            "expansions": [{"bgg_id": 13, "name": "Catan: Seafarers"}],
        },
        {
            "bgg_id": 13, "name_en": "Catan: Seafarers", "name_zh": "卡坦島：航海家",
            "description_en": "This expansion allows you to add seafaring to your Settlers of Catan game, with ships that serve as roads over water.",
            "description_zh": "這個擴充讓你在卡坦島遊戲中加入航海元素，船隻在水面上充當道路的功能。",
            "image": "https://cf.geekdo-images.com/itemrep/img/k4C7eW9GiMC3GziNavF5UhJ2uEs=/fit-in/246x300/pic1686968.jpg",
            "thumbnail": "https://cf.geekdo-images.com/thumb/img/A2gq6z2AHnPNx4jIQaJKVHqFySo=/fit-in/100x100/pic1686968.jpg",
            "bgg_rating": 7.21, "bgg_rank": 400, "bgg_weight": 2.40,
            "min_players": 3, "max_players": 4, "min_playtime": 60, "max_playtime": 120,
            "min_age": 10, "year_published": 1997, "users_rated": 22000,
            "categories": [{"id": 0, "name": "Economic"}, {"id": 1, "name": "Exploration"}],
            "mechanics": [{"id": 0, "name": "Dice Rolling"}, {"id": 1, "name": "Modular Board"}],
            "designers": ["Klaus Teuber"], "publishers": ["Kosmos"],
        },
        {
            "bgg_id": 3076, "name_en": "Carcassonne", "name_zh": "卡卡頌",
            "description_en": "Carcassonne is a tile-placement game in which players draw and place a tile with a piece of southern French landscape. The players develop the area around Carcassonne.",
            "description_zh": "卡卡頌是一款板塊放置遊戲，玩家抽取並放置描繪法國南部風景的板塊，圍繞卡卡頌城開發周邊地區。",
            "image": "https://cf.geekdo-images.com/itemrep/img/CqDi0R5Ha1q3K8FYFIu8bJDMqWk=/fit-in/246x300/pic2317566.jpg",
            "thumbnail": "https://cf.geekdo-images.com/thumb/img/T4V7X70x56HXdJ-BI7lxIi2DTyk=/fit-in/100x100/pic2317566.jpg",
            "bgg_rating": 7.42, "bgg_rank": 300, "bgg_weight": 1.84,
            "min_players": 2, "max_players": 5, "min_playtime": 30, "max_playtime": 45,
            "min_age": 8, "year_published": 2000, "users_rated": 78000,
            "categories": [{"id": 0, "name": "City Building"}, {"id": 1, "name": "Medieval"}],
            "mechanics": [{"id": 0, "name": "Tile Placement"}, {"id": 1, "name": "Area Control"}],
            "designers": ["Klaus-Jürgen Wrede"], "publishers": ["Hans im Glück"],
        },
        {
            "bgg_id": 68448, "name_en": "7 Wonders", "name_zh": "七大奇蹟",
            "description_en": "7 Wonders is a card development game using the drafting mechanic. Some cards have immediate effects, while others provide bonuses in the long run.",
            "description_zh": "七大奇蹟是一款使用輪抽機制的卡牌發展遊戲。有些卡牌有即時效果，而其他卡牌則提供長期加成。",
            "image": "https://cf.geekdo-images.com/itemrep/img/FkBub9snjD5XKq3q7KS9jf7F1V4=/fit-in/246x300/pic825698.jpg",
            "thumbnail": "https://cf.geekdo-images.com/thumb/img/mjjPPE5B9GBASLMzi0tqHkBKk1Y=/fit-in/100x100/pic825698.jpg",
            "bgg_rating": 7.70, "bgg_rank": 100, "bgg_weight": 2.34,
            "min_players": 3, "max_players": 7, "min_playtime": 30, "max_playtime": 30,
            "min_age": 10, "year_published": 2010, "users_rated": 58000,
            "categories": [{"id": 0, "name": "Ancient"}, {"id": 1, "name": "Card Game"}],
            "mechanics": [{"id": 0, "name": "Card Drafting"}, {"id": 1, "name": "Simultaneous Action"}],
            "designers": ["Antoine Bauza"], "publishers": ["Repos Production"],
        },
        {
            "bgg_id": 84876, "name_en": "The Castles of Burgundy", "name_zh": "勃根地城堡",
            "description_en": "The Castles of Burgundy is set in the Burgundy region of medieval France. Players take the roles of aristocrats controlling small princedoms.",
            "description_zh": "勃根地城堡背景設定在中世紀法國勃根地地區。玩家扮演控制小公國的貴族角色。",
            "image": "https://cf.geekdo-images.com/itemrep/img/H2jrMB3HY5kG9IW5xIM4JTsG0YI=/fit-in/246x300/pic1176894.jpg",
            "thumbnail": "https://cf.geekdo-images.com/thumb/img/9CWY4JO3kKm9a7RfbF9cJ0dAqy8=/fit-in/100x100/pic1176894.jpg",
            "bgg_rating": 8.06, "bgg_rank": 15, "bgg_weight": 2.94,
            "min_players": 2, "max_players": 4, "min_playtime": 30, "max_playtime": 90,
            "min_age": 12, "year_published": 2011, "users_rated": 35000,
            "categories": [{"id": 0, "name": "Economic"}, {"id": 1, "name": "Medieval"}],
            "mechanics": [{"id": 0, "name": "Dice Rolling"}, {"id": 1, "name": "Tile Placement"}, {"id": 2, "name": "Worker Placement"}],
            "designers": ["Stefan Feld"], "publishers": ["Ravensburger"],
        },
        {
            "bgg_id": 1406, "name_en": "Monopoly", "name_zh": "大富翁",
            "description_en": "Monopoly is a roll-and-move game where players travel around the board buying, renting, and trading properties.",
            "description_zh": "大富翁是一款擲骰移動遊戲，玩家在棋盤上行走，購買、出租和交易地產。",
            "image": "https://cf.geekdo-images.com/itemrep/img/6bBP4R9zpJXyGxxrF3hWGxfxC2g=/fit-in/246x300/pic1575123.jpg",
            "thumbnail": "https://cf.geekdo-images.com/thumb/img/Df8V7UD9Y2id8Ad0wLW5nEB28JM=/fit-in/100x100/pic1575123.jpg",
            "bgg_rating": 4.38, "bgg_rank": 9999, "bgg_weight": 1.28,
            "min_players": 2, "max_players": 8, "min_playtime": 60, "max_playtime": 180,
            "min_age": 8, "year_published": 1935, "users_rated": 55000,
            "categories": [{"id": 0, "name": "Economic"}, {"id": 1, "name": "Negotiation"}],
            "mechanics": [{"id": 0, "name": "Dice Rolling"}, {"id": 1, "name": "Roll / Spin and Move"}, {"id": 2, "name": "Trading"}],
            "designers": ["Charles Darrow"], "publishers": ["Hasbro"],
        },
        {
            "bgg_id": 1032, "name_en": "Ticket to Ride", "name_zh": "鐵道任務",
            "description_en": "Ticket to Ride is a cross-country train adventure where players collect cards of various types of train cars to claim railway routes across North America.",
            "description_zh": "鐵道任務是一場跨國鐵路冒險，玩家收集不同類型的火車車廂卡牌，以宣佈北美各地的鐵路路線。",
            "image": "https://cf.geekdo-images.com/itemrep/img/Y2E7_doZEcZbJIp_yM3KkUGdvao=/fit-in/246x300/pic384321.jpg",
            "thumbnail": "https://cf.geekdo-images.com/thumb/img/L0twM3v3tY6YBsX3KdJb8r1vBZI=/fit-in/100x100/pic384321.jpg",
            "bgg_rating": 7.43, "bgg_rank": 250, "bgg_weight": 1.82,
            "min_players": 2, "max_players": 5, "min_playtime": 30, "max_playtime": 60,
            "min_age": 8, "year_published": 2004, "users_rated": 62000,
            "categories": [{"id": 0, "name": "Trains"}, {"id": 1, "name": "Route Building"}],
            "mechanics": [{"id": 0, "name": "Set Collection"}, {"id": 1, "name": "Route Building"}],
            "designers": ["Alan R. Moon"], "publishers": ["Days of Wonder"],
        },
        {
            "bgg_id": 256814, "name_en": "Wingspan", "name_zh": "展翅翱翔",
            "description_en": "Wingspan is a competitive bird-collection, engine-building game. You are bird enthusiasts seeking to attract birds to your wildlife preserves.",
            "description_zh": "展翅翱翔是一款競爭性的鳥類收藏、引擎構建遊戲。你是鳥類愛好者，試圖吸引鳥類到你的野生動物保護區。",
            "image": "https://cf.geekdo-images.com/itemrep/img/j2sbKCTsHP6nlj5-X6HIwGDaLZc=/fit-in/246x300/pic4193755.jpg",
            "thumbnail": "https://cf.geekdo-images.com/thumb/img/FkHgc6Y9OsGPxl9_5kNMCT5n0-8=/fit-in/100x100/pic4193755.jpg",
            "bgg_rating": 8.10, "bgg_rank": 20, "bgg_weight": 2.42,
            "min_players": 1, "max_players": 5, "min_playtime": 40, "max_playtime": 70,
            "min_age": 10, "year_published": 2019, "users_rated": 46000,
            "categories": [{"id": 0, "name": "Animals"}, {"id": 1, "name": "Card Game"}],
            "mechanics": [{"id": 0, "name": "Card Drafting"}, {"id": 1, "name": "Set Collection"}, {"id": 2, "name": "Engine Building"}],
            "designers": ["Elizabeth Hargrave"], "publishers": ["Stonemaier Games"],
            "expansions": [{"bgg_id": 266192, "name": "Wingspan: European Expansion"}],
        },
        {
            "bgg_id": 266192, "name_en": "Wingspan: European Expansion", "name_zh": "展翅翱翔：歐洲擴充",
            "description_en": "The European Expansion adds new birds, bonus cards, and end-of-round goals to Wingspan, with a focus on European bird species.",
            "description_zh": "歐洲擴充為展翅翱翔新增了新鳥類、獎勵卡牌和回合結束目標，著重於歐洲鳥類物種。",
            "image": "https://cf.geekdo-images.com/itemrep/img/4fU2w6b2R2bRn1IWnMEi3E0mkR4=/fit-in/246x300/pic4459886.jpg",
            "thumbnail": "https://cf.geekdo-images.com/thumb/img/CqyVWHOT3iLwfm0qiKx9O9MFQJo=/fit-in/100x100/pic4459886.jpg",
            "bgg_rating": 8.22, "bgg_rank": 50, "bgg_weight": 2.48,
            "min_players": 1, "max_players": 5, "min_playtime": 40, "max_playtime": 70,
            "min_age": 10, "year_published": 2019, "users_rated": 12000,
            "categories": [{"id": 0, "name": "Animals"}, {"id": 1, "name": "Card Game"}],
            "mechanics": [{"id": 0, "name": "Card Drafting"}, {"id": 1, "name": "Set Collection"}],
            "designers": ["Elizabeth Hargrave"], "publishers": ["Stonemaier Games"],
        },
    ]

    for game in sample_games:
        game.setdefault("name_zh", "")
        game.setdefault("description_en", "")
        game.setdefault("description_zh", "")
        game.setdefault("thumbnail", "")
        game.setdefault("image", "")
        game.setdefault("local_thumbnail", "")
        game.setdefault("local_image", "")
        game.setdefault("min_age", 0)
        game.setdefault("users_rated", 0)
        game.setdefault("expansions", [])
        game.setdefault("series", [])
        game["updated_at"] = datetime.now(timezone.utc)

        await mongo_db.board_games.update_one(
            {"bgg_id": game["bgg_id"]},
            {"$set": game, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    print(f"Sample data import complete. {len(sample_games)} games saved.")
