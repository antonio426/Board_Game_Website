"""Re-run geekdo enricher for a specific list of bgg_ids.

Use this when you want to refresh the `aliases` field for known games
(e.g. Splendor family) without re-fetching the entire catalog.

Usage:
    cd backend && .venv/bin/python scripts/refresh_geekdo_ids.py 148228,293296,406291

The script calls the same geekdo API + parser as the main enricher
(`enrich_from_geekdo`), so it benefits from the updated
`_pick_all_cjk_names` logic that stores ALL CJK alternates into aliases.
"""
import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import httpx

from app.crawlers.geekdo_enricher import (
    GEEKDO_BASE,
    PER_REQUEST_SLEEP,
    REQUEST_TIMEOUT,
    _parse_game_payload,
)
from app.core.database import mongo_db, redis_client


def parse_ids(raw: str) -> list[int]:
    return [int(x) for x in raw.replace(",", " ").split() if x.strip()]


async def refresh_one(client: httpx.AsyncClient, bgg_id: int) -> dict:
    url = f"{GEEKDO_BASE}?objectid={bgg_id}&objecttype=thing&showstats=1"
    resp = await client.get(url)
    if resp.status_code != 200:
        return {"bgg_id": bgg_id, "ok": False, "error": f"HTTP {resp.status_code}"}
    payload = resp.json()
    update = _parse_game_payload(payload, bgg_id)
    update.pop("bgg_id", None)
    if not update:
        return {"bgg_id": bgg_id, "ok": False, "error": "empty update"}
    res = await mongo_db.board_games.update_one(
        {"bgg_id": bgg_id}, {"$set": update}
    )
    return {
        "bgg_id": bgg_id,
        "ok": True,
        "modified": res.modified_count,
        "aliases": update.get("aliases"),
        "name_zh": update.get("name_zh"),
    }


async def main(ids: list[int]) -> None:
    print(f"[refresh] targets={ids}")

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "BoardGameHub/1.0 (geekdo-enricher)"},
    ) as client:
        for bid in ids:
            try:
                result = await refresh_one(client, bid)
                if result["ok"]:
                    print(
                        f"  [{bid}] modified={result['modified']} "
                        f"name_zh={result['name_zh']!r} aliases={result['aliases']}"
                    )
                else:
                    print(f"  [{bid}] FAIL: {result['error']}")
            except Exception as e:
                print(f"  [{bid}] EXC: {e}")
            await asyncio.sleep(PER_REQUEST_SLEEP)

    try:
        redis_client.flushdb()
        print("[cache] Redis flushdb ok")
    except Exception as e:
        print(f"[cache] Redis flushdb failed (non-fatal): {e}")

    print()
    print("=== verification ===")
    for bid in ids:
        doc = await mongo_db.board_games.find_one(
            {"bgg_id": bid},
            projection={"name_en": 1, "name_zh": 1, "aliases": 1},
        )
        print(f"  [{bid}] {doc}")

    print()
    print("=== search test: q='璀璨寶石' ===")
    cur = mongo_db.board_games.find(
        {
            "$or": [
                {"name_en": {"$regex": "璀璨寶石", "$options": "i"}},
                {"name_zh": {"$regex": "璀璨寶石", "$options": "i"}},
                {"aliases": {"$regex": "璀璨寶石", "$options": "i"}},
            ]
        },
        projection={"bgg_id": 1, "name_en": 1, "name_zh": 1, "aliases": 1},
    ).limit(20)
    matches = [d async for d in cur]
    print(f"  {len(matches)} match(es):")
    for d in matches:
        print(
            f"    bgg_id={d.get('bgg_id')} name_en={d.get('name_en','')!r} "
            f"name_zh={d.get('name_zh','')!r} aliases={d.get('aliases')}"
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: refresh_geekdo_ids.py <bgg_id,bgg_id,...>")
        sys.exit(1)
    asyncio.run(main(parse_ids(sys.argv[1])))
