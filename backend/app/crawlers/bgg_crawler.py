import asyncio
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from app.core.database import mongo_db
from app.core.config import settings

BGG_API_BASE = "https://boardgamegeek.com/xmlapi2"
RATE_LIMIT_INTERVAL = 0.5
MAX_RETRIES = 5
TOP_GAMES_COUNT = 2000


class BGGCrawler:
    def __init__(self):
        initial_cookies = {}
        session_cookies_str = os.environ.get(
            "BGG_SESSION_COOKIES", settings.BGG_SESSION_COOKIES
        )
        if session_cookies_str:
            for pair in session_cookies_str.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    initial_cookies[k.strip()] = v.strip()

        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "application/xml, text/xml, */*",
            },
            follow_redirects=True,
            cookies=initial_cookies,
        )
        self._semaphore = asyncio.Semaphore(2)
        self._authenticated = bool(initial_cookies)

    async def close(self):
        await self.client.aclose()

    async def authenticate(self) -> bool:
        bgg_user = os.environ.get("BGG_USERNAME", settings.BGG_USERNAME)
        bgg_pass = os.environ.get("BGG_PASSWORD", settings.BGG_PASSWORD)
        if not bgg_user or not bgg_pass:
            print("BGG credentials not configured (BGG_USERNAME/BGG_PASSWORD)")
            return False
        if self._authenticated:
            return True
        try:
            resp = await self.client.post(
                "https://boardgamegeek.com/login",
                data={
                    "username": bgg_user,
                    "password": bgg_pass,
                    "action": "login",
                },
                follow_redirects=True,
            )
            if resp.status_code == 200 and "Sign Out" in resp.text:
                self._authenticated = True
                print("BGG authentication successful")
                return True
            print(f"BGG authentication failed: HTTP {resp.status_code}")
            return False
        except Exception as e:
            print(f"BGG authentication error: {e}")
            return False

    async def _fetch(self, url: str) -> str | None:
        for attempt in range(MAX_RETRIES):
            async with self._semaphore:
                try:
                    await asyncio.sleep(RATE_LIMIT_INTERVAL * (attempt + 1))
                    resp = await self.client.get(url)
                    if resp.status_code == 200:
                        return resp.text
                    if resp.status_code == 401:
                        if not self._authenticated:
                            auth_ok = await self.authenticate()
                            if auth_ok:
                                continue
                        print(f"BGG API 401 Unauthorized - set BGG_SESSION_COOKIES or BGG_USERNAME/BGG_PASSWORD")
                        return None
                    if resp.status_code == 429:
                        wait = 2 ** attempt * 5
                        print(f"Rate limited, waiting {wait}s...")
                        await asyncio.sleep(wait)
                        continue
                    if resp.status_code == 202:
                        await asyncio.sleep(3)
                        continue
                    print(f"HTTP {resp.status_code} for {url}")
                except Exception as e:
                    print(f"Error fetching {url}: {e}")
                    await asyncio.sleep(2 ** attempt)
        return None

    async def fetch_top_game_ids(self) -> list[int]:
        ids = []
        page = 1
        while len(ids) < TOP_GAMES_COUNT:
            url = f"https://boardgamegeek.com/search/boardgame?page={page}&sort=rank&advsearch=1"
            html = await self._fetch(url)
            if not html:
                break
            page_ids = self._parse_search_ids(html)
            if not page_ids:
                break
            ids.extend(page_ids)
            print(f"Page {page}: found {len(page_ids)} games, total {len(ids)}")
            page += 1
            if len(page_ids) < 50:
                break
        return ids[:TOP_GAMES_COUNT]

    def _parse_search_ids(self, html: str) -> list[int]:
        import re
        return [int(m) for m in re.findall(r'/boardgame/(\d+)', html) if int(m) > 100]

    async def fetch_game_data(self, bgg_ids: list[int]) -> list[dict]:
        results = []
        batch_size = 20
        for i in range(0, len(bgg_ids), batch_size):
            batch = bgg_ids[i:i + batch_size]
            ids_str = ",".join(str(id) for id in batch)
            url = f"{BGG_API_BASE}/thing?id={ids_str}&stats=1&type=boardgame,boardgameexpansion"
            xml_text = await self._fetch(url)
            if xml_text:
                games = self._parse_thing_xml(xml_text)
                results.extend(games)
                print(f"Fetched {len(games)} games ({i + len(batch)}/{len(bgg_ids)})")
        return results

    def _parse_thing_xml(self, xml_text: str) -> list[dict]:
        games = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return games

        for item in root.findall("item"):
            if item.get("type") not in ("boardgame", "boardgameexpansion"):
                continue

            bgg_id = int(item.get("id", 0))
            name_en = ""
            for n in item.findall("name"):
                if n.get("type") == "primary":
                    name_en = n.get("value", "")
                    break
            if not name_en:
                for n in item.findall("name"):
                    name_en = n.get("value", "")
                    break

            description = item.findtext("description", "")
            thumbnail = item.findtext("thumbnail", "")
            image = item.findtext("image", "")

            min_players = self._safe_int(item, "minplayers", "value")
            max_players = self._safe_int(item, "maxplayers", "value")
            min_playtime = self._safe_int(item, "minplaytime", "value")
            max_playtime = self._safe_int(item, "maxplaytime", "value")
            min_age = self._safe_int(item, "minage", "value")
            year_published = self._safe_int(item, "yearpublished", "value")

            categories = []
            mechanics = []
            expansions = []
            series = []
            designers = []
            publishers = []

            for link in item.findall("link"):
                link_type = link.get("type", "")
                link_id = int(link.get("id", 0))
                link_name = link.get("value", "")
                if link_type == "boardgamecategory":
                    categories.append({"id": link_id, "name": link_name})
                elif link_type == "boardgamemechanic":
                    mechanics.append({"id": link_id, "name": link_name})
                elif link_type == "boardgameexpansion":
                    expansions.append({"bgg_id": link_id, "name": link_name})
                elif link_type == "boardgamecompilation":
                    series.append({"bgg_id": link_id, "name": link_name})
                elif link_type == "boardgamedesigner":
                    designers.append(link_name)
                elif link_type == "boardgamepublisher":
                    publishers.append(link_name)

            stats = item.find("statistics/ratings")
            bgg_rating = 0.0
            bgg_rank = 99999
            bgg_weight = 0.0
            users_rated = 0
            if stats is not None:
                bgg_rating = float(stats.findtext("average", "0"))
                users_rated = int(stats.findtext("usersrated", "0"))
                bgg_weight = float(stats.findtext("averageweight", "0"))
                for rank_elem in stats.findall("ranks/rank"):
                    if rank_elem.get("name") == "boardgame":
                        try:
                            bgg_rank = int(rank_elem.get("value", "99999"))
                        except ValueError:
                            bgg_rank = 99999
                        break

            game_doc = {
                "bgg_id": bgg_id,
                "name_en": name_en,
                "name_zh": "",
                "description_en": description,
                "description_zh": "",
                "thumbnail": thumbnail,
                "image": image,
                "local_thumbnail": "",
                "local_image": "",
                "year_published": year_published,
                "min_players": min_players,
                "max_players": max_players,
                "min_playtime": min_playtime,
                "max_playtime": max_playtime,
                "min_age": min_age,
                "bgg_rating": round(bgg_rating, 2),
                "bgg_rank": bgg_rank,
                "bgg_weight": round(bgg_weight, 2),
                "users_rated": users_rated,
                "categories": categories,
                "mechanics": mechanics,
                "expansions": expansions,
                "series": series,
                "designers": designers,
                "publishers": publishers,
                "updated_at": datetime.now(timezone.utc),
            }
            games.append(game_doc)

        return games

    @staticmethod
    def _safe_int(item: ET.Element, child_name: str, attr: str) -> int:
        child = item.find(child_name)
        if child is not None:
            try:
                return int(child.get(attr, "0"))
            except (ValueError, TypeError):
                return 0
        return 0

    async def search_bgg(self, name: str) -> list[dict]:
        """Search BGG by name and return list of {bgg_id, name} matches."""
        url = f"{BGG_API_BASE}/search?query={name}&type=boardgame,boardgameexpansion"
        xml_text = await self._fetch(url)
        if not xml_text:
            return []
        results = []
        try:
            root = ET.fromstring(xml_text)
            for item in root.findall("item"):
                bgg_id = int(item.get("id", 0))
                name_en = ""
                for n in item.findall("name"):
                    if n.get("type") == "primary":
                        name_en = n.get("value", "")
                        break
                if not name_en:
                    for n in item.findall("name"):
                        name_en = n.get("value", "")
                        break
                if bgg_id and name_en:
                    results.append({"bgg_id": bgg_id, "name": name_en})
        except ET.ParseError:
            pass
        return results

    async def fetch_game_geekdo(self, bgg_id: int) -> dict | None:
        """Fetch a single game via the unauthenticated Geekdo JSON API."""
        url = f"https://api.geekdo.com/api/geekitems?objecttype=thing&objectid={bgg_id}"
        try:
            resp = await self.client.get(url, headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://boardgamegeek.com/",
            })
            if resp.status_code != 200:
                print(f"Geekdo API HTTP {resp.status_code} for bgg_id={bgg_id}")
                return None
            data = resp.json()
            item = data.get("item")
            if not item:
                return None
            return self._parse_geekdo_item(item)
        except Exception as e:
            print(f"Geekdo fetch error for bgg_id={bgg_id}: {e}")
            return None

    def _parse_geekdo_item(self, item: dict) -> dict:
        """Convert a Geekdo API item dict to our game_doc schema."""
        bgg_id = int(item.get("objectid", 0))
        name_en = item.get("name", "") or item.get("primaryname", "")
        description = item.get("description", "")
        year_published = int(item.get("yearpublished", 0) or 0)
        min_players = int(item.get("minplayers", 0) or 0)
        max_players = int(item.get("maxplayers", 0) or 0)
        min_playtime = int(item.get("minplaytime", 0) or 0)
        max_playtime = int(item.get("maxplaytime", 0) or 0)
        min_age = int(item.get("minage", 0) or 0)

        # Images — Geekdo uses multiple image URL keys
        image = item.get("imageurl", "") or item.get("topimageurl", "") or ""
        thumbnail = item.get("imageurl", "") or ""

        # Links — categories, mechanics, designers, publishers
        links = item.get("links", {})
        categories = []
        mechanics = []
        designers = []
        publishers = []
        expansions = []
        series = []

        for cat in links.get("boardgamecategory", []):
            categories.append({"id": int(cat.get("objectid", 0)), "name": cat.get("name", "")})
        for mech in links.get("boardgamemechanic", []):
            mechanics.append({"id": int(mech.get("objectid", 0)), "name": mech.get("name", "")})
        for des in links.get("boardgamedesigner", []):
            designers.append(des.get("name", ""))
        for pub in links.get("boardgamepublisher", []):
            publishers.append(pub.get("name", ""))
        for exp in links.get("boardgameexpansion", []):
            expansions.append({"bgg_id": int(exp.get("objectid", 0)), "name": exp.get("name", "")})
        for fam in links.get("boardgamefamily", []):
            series.append({"bgg_id": int(fam.get("objectid", 0)), "name": fam.get("name", "")})

        # Stats — Geekdo itemdata may have rank/rating; fall back to 0
        itemdata = item.get("itemdata", {}) or {}
        bgg_rank = int(itemdata.get("boardgame_rank", 99999) or 99999)
        bgg_rating = float(itemdata.get("avg_rating", 0) or 0)
        bgg_weight = float(itemdata.get("avg_weight", 0) or 0)
        users_rated = int(itemdata.get("num_votes", 0) or 0)

        # If itemdata is empty, try top-level stats fields
        if not itemdata:
            bgg_rating = float(item.get("avg_rating", 0) or 0)
            users_rated = int(item.get("num_votes", 0) or 0)

        return {
            "bgg_id": bgg_id,
            "name_en": name_en,
            "name_zh": "",
            "description_en": description,
            "description_zh": "",
            "thumbnail": thumbnail,
            "image": image,
            "local_thumbnail": "",
            "local_image": "",
            "year_published": year_published,
            "min_players": min_players,
            "max_players": max_players,
            "min_playtime": min_playtime,
            "max_playtime": max_playtime,
            "min_age": min_age,
            "bgg_rating": round(bgg_rating, 2),
            "bgg_rank": bgg_rank,
            "bgg_weight": round(bgg_weight, 2),
            "users_rated": users_rated,
            "categories": categories,
            "mechanics": mechanics,
            "expansions": expansions,
            "series": series,
            "designers": designers,
            "publishers": publishers,
            "updated_at": datetime.now(timezone.utc),
        }

    async def search_bga(self, name: str, limit: int = 5) -> list[dict]:
        """Search BoardGameAtlas by name; returns list of {bgg_id, name}."""
        bga_client_id = "JSKF2J3VYH"
        url = f"https://api.boardgameatlas.com/api/search?name={name}&client_id={bga_client_id}&limit={limit}"
        try:
            resp = await self.client.get(url, headers={
                "Accept": "application/json",
            })
            if resp.status_code != 200:
                print(f"BGA search HTTP {resp.status_code} for q={name}")
                return []
            data = resp.json()
            results = []
            for g in data.get("games", []):
                bgg_id_str = g.get("bgg_id")
                if bgg_id_str:
                    try:
                        bgg_id = int(bgg_id_str)
                        if bgg_id > 0:
                            results.append({"bgg_id": bgg_id, "name": g.get("name", "")})
                    except (ValueError, TypeError):
                        continue
            return results
        except Exception as e:
            print(f"BGA search error for q={name}: {e}")
            return []

    async def fetch_and_save_game(self, bgg_id: int) -> dict | None:
        """Fetch a single game by ID, save to DB, return the game doc or None.

        Tries the unauthenticated Geekdo API first; falls back to BGG XMLAPI2
        (which requires auth).
        """
        game = await self.fetch_game_geekdo(bgg_id)
        if game and game.get("description_en"):
            await self.save_games([game])
            return game

        # Fallback: XMLAPI2 (requires auth)
        print(f"Geekdo returned no data for bgg_id={bgg_id}, trying XMLAPI2 fallback")
        games = await self.fetch_game_data([bgg_id])
        if not games:
            return None
        await self.save_games(games)
        return games[0]

    async def save_games(self, games: list[dict]):
        if not games:
            return
        collection = mongo_db.board_games
        for game in games:
            await collection.update_one(
                {"bgg_id": game["bgg_id"]},
                {
                    "$set": game,
                    "$setOnInsert": {
                        "created_at": datetime.now(timezone.utc),
                    },
                },
                upsert=True,
            )
        print(f"Saved {len(games)} games to MongoDB")

    async def run(self, limit: int = TOP_GAMES_COUNT):
        print(f"Starting BGG crawler (top {limit} games)...")
        try:
            if BGG_USERNAME and BGG_PASSWORD:
                await self.authenticate()

            print("Fetching top game IDs from BGG search...")
            ids = await self.fetch_top_game_ids()
            print(f"Found {len(ids)} game IDs")

            ids = ids[:limit]
            games = await self.fetch_game_data(ids)
            await self.save_games(games)
            print(f"Crawling complete. Saved {len(games)} games.")
        finally:
            await self.close()
