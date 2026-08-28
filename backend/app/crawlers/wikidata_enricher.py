import asyncio
import os
from difflib import SequenceMatcher

import httpx
import pymongo

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB_NAME", "boardgame")
MONGO_USER = os.environ.get("MONGO_USER", "boardgame")
MONGO_PASS = os.environ.get("MONGO_PASS", "boardgame_dev")

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
BGG_PROPERTY = "P2339"
BATCH_SIZE = 200
MIN_RATIO = 0.5


async def fetch_wikidata_zh_names(bgg_ids: list[int]) -> dict[int, str]:
    result = {}
    headers = {
        "Accept": "application/json",
        "User-Agent": "BoardGameHub/1.0 (wikidata-enrichment)",
    }

    async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:
        for i in range(0, len(bgg_ids), BATCH_SIZE):
            batch = bgg_ids[i : i + BATCH_SIZE]
            ids_str = " ".join(f'"{bid}"' for bid in batch)

            query = f"""
            SELECT ?bggId ?nameEn ?nameZh ?nameZhHans WHERE {{
              ?game wdt:{BGG_PROPERTY} ?bggId .
              VALUES ?bggId {{ {ids_str} }}
              OPTIONAL {{ ?game rdfs:label ?nameEn . FILTER(lang(?nameEn)="en") }}
              OPTIONAL {{ ?game rdfs:label ?nameZh . FILTER(lang(?nameZh)="zh") }}
              OPTIONAL {{ ?game rdfs:label ?nameZhHans . FILTER(lang(?nameZhHans)="zh-hans") }}
            }}
            """

            try:
                resp = await client.get(
                    SPARQL_ENDPOINT, params={"query": query, "format": "json"}
                )
                if resp.status_code != 200:
                    print(f"Wikidata batch {i // BATCH_SIZE + 1}: HTTP {resp.status_code}")
                    continue

                data = resp.json()
                for b in data.get("results", {}).get("bindings", []):
                    bgg_id = b.get("bggId", {}).get("value", "")
                    en = b.get("nameEn", {}).get("value", "")
                    zh = b.get("nameZh", {}).get("value", "")
                    zh_hans = b.get("nameZhHans", {}).get("value", "")
                    zh_name = zh_hans or zh
                    if bgg_id and zh_name:
                        try:
                            bgg_id_int = int(bgg_id)
                            if bgg_id_int not in result:
                                result[bgg_id_int] = {"en": en, "zh": zh_name}
                        except ValueError:
                            continue

                await asyncio.sleep(1)
            except Exception as e:
                print(f"Wikidata batch {i // BATCH_SIZE + 1} error: {e}")

    return result


async def enrich_zh_from_wikidata(min_ratio: float = MIN_RATIO, max_rank: int | None = None):
    mongo_uri = f"mongodb://{MONGO_USER}:{MONGO_PASS}@localhost:27017"
    client = pymongo.MongoClient(mongo_uri)
    db = client[MONGO_DB]

    needs_zh_filter: dict = {
        "description_en": {"$exists": True, "$ne": ""},
        "$or": [{"name_zh": ""}, {"name_zh": {"$exists": False}}],
    }
    if max_rank is not None:
        needs_zh_filter["bgg_rank"] = {"$gt": 0, "$lte": max_rank}

    needs_zh = list(
        db.board_games.find(
            needs_zh_filter,
            {"bgg_id": 1, "name_en": 1},
        )
    )

    bgg_ids = [g["bgg_id"] for g in needs_zh]
    our_games = {g["bgg_id"]: g for g in needs_zh}
    print(f"Games needing zh names: {len(bgg_ids)}")

    wikidata = await fetch_wikidata_zh_names(bgg_ids)
    print(f"Wikidata zh names found: {len(wikidata)}")

    updated = 0
    for bgg_id, wd in wikidata.items():
        if bgg_id not in our_games:
            continue

        our_en = our_games[bgg_id].get("name_en", "")
        wd_en = wd["en"]
        ratio = SequenceMatcher(
            None, our_en.lower().strip(), wd_en.lower().strip()
        ).ratio()

        if ratio >= min_ratio:
            db.board_games.update_one({"bgg_id": bgg_id}, {"$set": {"name_zh": wd["zh"]}})
            updated += 1

    print(f"Updated {updated} games with verified Wikidata zh names")

    try:
        import redis

        r = redis.Redis(host="localhost", port=6379, db=0)
        r.flushdb()
        print("Redis cache flushed")
    except Exception:
        print("Redis flush skipped")

    client.close()
    return updated


if __name__ == "__main__":
    asyncio.run(enrich_zh_from_wikidata())
