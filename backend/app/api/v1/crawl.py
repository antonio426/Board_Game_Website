import asyncio
from typing import Optional
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.crawlers.bgg_crawler import BGGCrawler
from app.crawlers.csv_importer import import_sample_data
from app.crawlers.extra_games import import_extra_data
from app.core.database import mongo_db, redis_client

router = APIRouter(prefix="/crawl", tags=["crawl"])

_crawl_status = {"running": False, "progress": "", "count": 0}


class BGGSessionCookies(BaseModel):
    cookies: str


@router.post("/bgg/cookies")
async def set_bgg_cookies(body: BGGSessionCookies):
    import os
    os.environ["BGG_SESSION_COOKIES"] = body.cookies
    crawler = BGGCrawler()
    test_url = "https://boardgamegeek.com/xmlapi2/thing?id=174430&stats=1"
    resp = await crawler.client.get(test_url)
    await crawler.close()
    if resp.status_code == 200:
        return {"status": "ok", "message": "Cookies valid - BGG API accessible"}
    return {"status": "error", "message": f"API returned HTTP {resp.status_code}", "hint": "Copy cookies from browser DevTools > Application > Cookies for boardgamegeek.com"}


@router.post("/bgg")
async def start_bgg_crawl(background_tasks: BackgroundTasks, limit: int = 100):
    if _crawl_status["running"]:
        return {"status": "already_running", "message": "Crawler is already running"}

    _crawl_status["running"] = True
    _crawl_status["progress"] = "starting"
    _crawl_status["count"] = 0

    async def _run():
        crawler = BGGCrawler()
        try:
            _crawl_status["progress"] = "fetching_ids"
            ids = await crawler.fetch_top_game_ids()
            ids = ids[:limit]
            _crawl_status["progress"] = f"fetching_data_0_{len(ids)}"
            games = await crawler.fetch_game_data(ids)
            await crawler.save_games(games)
            _crawl_status["count"] = len(games)
            _crawl_status["progress"] = "done"
        except Exception as e:
            _crawl_status["progress"] = f"error: {e}"
        finally:
            _crawl_status["running"] = False
            await crawler.close()

    background_tasks.add_task(_run)
    return {"status": "started", "limit": limit}


@router.get("/bgg/status")
async def crawl_status():
    return _crawl_status


@router.get("/bgg/count")
async def game_count():
    count = await mongo_db.board_games.count_documents({})
    return {"count": count}


@router.post("/sample")
async def load_sample_data():
    await import_sample_data()
    await import_extra_data()
    from app.api.v1.translate import translate_terms
    await translate_terms()
    try:
        redis_client.flushdb()
    except Exception:
        pass
    count = await mongo_db.board_games.count_documents({})
    return {"status": "ok", "count": count}


@router.post("/database")
async def load_bgg_database(background_tasks: BackgroundTasks):
    if _crawl_status["running"]:
        return {"status": "already_running"}

    _crawl_status["running"] = True
    _crawl_status["progress"] = "importing_bgg_database"
    _crawl_status["count"] = 0

    async def _run():
        try:
            from app.crawlers.db_importer import import_bgg_database, import_all_local_images
            from app.api.v1.translate import translate_terms
            await import_bgg_database()
            await import_all_local_images()
            await translate_terms(batch_size=500)
            try:
                redis_client.flushdb()
            except Exception:
                pass
            _crawl_status["count"] = await mongo_db.board_games.count_documents({})
            _crawl_status["progress"] = "done"
        except Exception as e:
            _crawl_status["progress"] = f"error: {e}"
        finally:
            _crawl_status["running"] = False

    background_tasks.add_task(_run)
    return {"status": "started"}


@router.post("/official-dump")
async def load_official_dump(background_tasks: BackgroundTasks, csv_path: str = "/tmp/bgg_rankings_official.csv"):
    if _crawl_status["running"]:
        return {"status": "already_running"}

    _crawl_status["running"] = True
    _crawl_status["progress"] = "importing_official_bgg_dump"
    _crawl_status["count"] = 0

    async def _run():
        try:
            from app.crawlers.csv_importer import import_bgg_csv
            await import_bgg_csv(csv_path)
            try:
                redis_client.flushdb()
            except Exception:
                pass
            _crawl_status["count"] = await mongo_db.board_games.count_documents({})
            _crawl_status["progress"] = "done"
        except Exception as e:
            _crawl_status["progress"] = f"error: {e}"
        finally:
            _crawl_status["running"] = False

    background_tasks.add_task(_run)
    return {"status": "started", "csv_path": csv_path}


@router.post("/wikidata")
async def enrich_wikidata_zh(
    background_tasks: BackgroundTasks,
    max_rank: Optional[int] = None,
):
    if _crawl_status["running"]:
        return {"status": "already_running"}

    _crawl_status["running"] = True
    _crawl_status["progress"] = "enriching_zh_from_wikidata"
    _crawl_status["count"] = 0

    async def _run():
        try:
            from app.crawlers.wikidata_enricher import enrich_zh_from_wikidata
            updated = await enrich_zh_from_wikidata(max_rank=max_rank)
            _crawl_status["count"] = updated
            _crawl_status["progress"] = "done"
        except Exception as e:
            _crawl_status["progress"] = f"error: {e}"
        finally:
            _crawl_status["running"] = False

    background_tasks.add_task(_run)
    return {"status": "started", "max_rank": max_rank}


@router.post("/geekdo-enrich")
async def enrich_geekdo(
    background_tasks: BackgroundTasks,
    limit: int = 100,
    only_missing: bool = True,
    max_rank: Optional[int] = None,
    min_rank: Optional[int] = None,
):
    if _crawl_status["running"]:
        return {"status": "already_running"}

    _crawl_status["running"] = True
    _crawl_status["progress"] = "enriching_from_geekdo_api"
    _crawl_status["count"] = 0

    async def _run():
        try:
            from app.crawlers.geekdo_enricher import enrich_from_geekdo
            stats = await enrich_from_geekdo(
                limit=limit,
                only_missing=only_missing,
                max_rank=max_rank,
                min_rank=min_rank,
            )
            _crawl_status["count"] = stats.get("updated", 0)
            _crawl_status["progress"] = "done"
        except Exception as e:
            _crawl_status["progress"] = f"error: {e}"
        finally:
            _crawl_status["running"] = False

    background_tasks.add_task(_run)
    return {
        "status": "started",
        "limit": limit,
        "only_missing": only_missing,
        "min_rank": min_rank,
        "max_rank": max_rank,
    }
