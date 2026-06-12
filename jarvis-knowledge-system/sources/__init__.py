"""
Source modules for the JARVIS Knowledge Engine.
Handles fetching from Wikipedia, Wikidata, web search, news feeds, and local files.
"""

import json
import os
import logging
import asyncio
import hashlib
from datetime import datetime, timedelta
from urllib.parse import quote

logger = logging.getLogger("jarvis.sources")


class Cache:
    """Simple file-based cache for API responses."""

    def __init__(self, cache_dir, ttl=3600):
        self.cache_dir = cache_dir
        self.ttl = ttl
        os.makedirs(cache_dir, exist_ok=True)

    def _path(self, key):
        h = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{h}.json")

    def get(self, key):
        path = self._path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            timestamp = datetime.fromisoformat(data["_cached_at"])
            if datetime.now() - timestamp > timedelta(seconds=self.ttl):
                return None
            return data["result"]
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def set(self, key, result):
        path = self._path(key)
        data = {"_cached_at": datetime.now().isoformat(), "result": result}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


class WikipediaSource:
    """Fetch knowledge from Wikipedia API."""

    def __init__(self, language="en", timeout=10, cache=None):
        self.language = language
        self.timeout = timeout
        self.cache = cache
        self.name = "wikipedia"
        self.reliability = 0.85

    async def search(self, query, max_results=3):
        cache_key = f"wiki_search:{query}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        try:
            import aiohttp
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "format": "json",
                "utf8": 1,
            }
            url = f"https://{self.language}.wikipedia.org/w/api.php"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=self.timeout) as resp:
                    data = await resp.json()
                    results = []
                    for item in data.get("query", {}).get("search", []):
                        results.append({
                            "title": item["title"],
                            "snippet": item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", ""),
                            "page_id": item["pageid"],
                            "source": self.name,
                            "url": f"https://{self.language}.wikipedia.org/wiki/{quote(item['title'].replace(' ', '_'))}",
                        })
                    if self.cache:
                        self.cache.set(cache_key, results)
                    return results
        except Exception as e:
            logger.warning(f"Wikipedia search failed: {e}")
            return []

    async def get_page(self, title):
        """Get full page content from Wikipedia."""
        cache_key = f"wiki_page:{title}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        try:
            import aiohttp
            params = {
                "action": "query",
                "titles": title,
                "prop": "extracts|info",
                "exintro": 1,
                "explaintext": 1,
                "inprop": "url",
                "format": "json",
                "utf8": 1,
            }
            url = f"https://{self.language}.wikipedia.org/w/api.php"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=self.timeout) as resp:
                    data = await resp.json()
                    pages = data.get("query", {}).get("pages", {})
                    for page_id, page in pages.items():
                        if page_id == "-1":
                            continue
                        result = {
                            "title": page.get("title", title),
                            "extract": page.get("extract", ""),
                            "url": page.get("fullurl", ""),
                            "source": self.name,
                        }
                        if self.cache:
                            self.cache.set(cache_key, result)
                        return result
        except Exception as e:
            logger.warning(f"Wikipedia page fetch failed: {e}")
        return None


class WikidataSource:
    """Fetch structured data from Wikidata API."""

    def __init__(self, timeout=10, cache=None):
        self.timeout = timeout
        self.cache = cache
        self.name = "wikidata"
        self.reliability = 0.9

    async def search(self, query, max_results=3):
        cache_key = f"wikidata_search:{query}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        try:
            import aiohttp
            params = {
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "limit": max_results,
                "format": "json",
            }
            url = "https://www.wikidata.org/w/api.php"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=self.timeout) as resp:
                    data = await resp.json()
                    results = []
                    for item in data.get("search", []):
                        results.append({
                            "id": item["id"],
                            "label": item.get("label", ""),
                            "description": item.get("description", ""),
                            "source": self.name,
                            "url": f"https://www.wikidata.org/wiki/{item['id']}",
                        })
                    if self.cache:
                        self.cache.set(cache_key, results)
                    return results
        except Exception as e:
            logger.warning(f"Wikidata search failed: {e}")
            return []

    async def get_entity(self, entity_id):
        """Get full entity data from Wikidata."""
        cache_key = f"wikidata_entity:{entity_id}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        try:
            import aiohttp
            params = {
                "action": "wbgetentities",
                "ids": entity_id,
                "languages": "en",
                "format": "json",
            }
            url = "https://www.wikidata.org/w/api.php"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=self.timeout) as resp:
                    data = await resp.json()
                    entity = data.get("entities", {}).get(entity_id, {})
                    if entity:
                        result = {
                            "id": entity_id,
                            "label": entity.get("labels", {}).get("en", {}).get("value", ""),
                            "description": entity.get("descriptions", {}).get("en", {}).get("value", ""),
                            "aliases": [a.get("value") for a in entity.get("aliases", {}).get("en", [])],
                            "claims": entity.get("claims", {}),
                            "source": self.name,
                        }
                        if self.cache:
                            self.cache.set(cache_key, result)
                        return result
        except Exception as e:
            logger.warning(f"Wikidata entity fetch failed: {e}")
        return None


class WebSearchSource:
    """Search the web using DuckDuckGo or similar."""

    def __init__(self, timeout=15, cache=None):
        self.timeout = timeout
        self.cache = cache
        self.name = "web_search"
        self.reliability = 0.6

    async def search(self, query, max_results=5):
        cache_key = f"web_search:{query}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        try:
            import aiohttp
            from bs4 import BeautifulSoup

            # DuckDuckGo HTML search (no API key needed)
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0 (compatible; JARVIS-Knowledge-Engine)"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=self.timeout) as resp:
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")
                    results = []
                    for item in soup.select(".result")[:max_results]:
                        title_el = item.select_one(".result__title a")
                        snippet_el = item.select_one(".result__snippet")
                        if title_el:
                            results.append({
                                "title": title_el.get_text(strip=True),
                                "url": title_el.get("href", ""),
                                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                                "source": self.name,
                            })
                    if self.cache:
                        self.cache.set(cache_key, results)
                    return results
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
            return []


class NewsSource:
    """Fetch recent news from RSS feeds."""

    def __init__(self, timeout=10, cache=None):
        self.timeout = timeout
        self.cache = cache
        self.name = "news"
        self.reliability = 0.7
        self.feeds = [
            "http://rss.cnn.com/rss/cnn_topstories.rss",
            "http://feeds.bbc.co.uk/news/rss.xml",
        ]

    async def search(self, query, max_results=5):
        cache_key = f"news_search:{query}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        try:
            import aiohttp
            from bs4 import BeautifulSoup
            import xml.etree.ElementTree as ET

            results = []
            for feed_url in self.feeds:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(feed_url, timeout=self.timeout) as resp:
                            content = await resp.text()
                            root = ET.fromstring(content)
                            ns = {"": "http://www.w3.org/2005/Atom"}
                            for entry in root.findall(".//item", ns) or root.findall(".//entry", ns):
                                title = entry.findtext("title", "")
                                desc = entry.findtext("description", "") or entry.findtext("summary", "")
                                if query.lower() in title.lower() or query.lower() in desc.lower():
                                    results.append({
                                        "title": title,
                                        "snippet": desc,
                                        "source": self.name,
                                        "url": entry.findtext("link", "") or entry.findtext("id", ""),
                                    })
                                    if len(results) >= max_results:
                                        break
                except Exception as e:
                    logger.debug(f"News feed {feed_url} failed: {e}")
                    continue

            if self.cache:
                self.cache.set(cache_key, results)
            return results
        except Exception as e:
            logger.warning(f"News search failed: {e}")
            return []


class LocalFileSource:
    """Read knowledge from local JSON and text files."""

    def __init__(self, knowledge_dir):
        self.knowledge_dir = knowledge_dir
        self.name = "local"
        self.reliability = 0.95

    def search(self, query):
        """Search local JSON files. Synchronous."""
        results = []
        query_lower = query.lower()
        for fname in os.listdir(self.knowledge_dir):
            if fname.endswith(".json"):
                path = os.path.join(self.knowledge_dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for key, value in data.items():
                        if query_lower in key.lower() or query_lower in str(value).lower():
                            results.append({
                                "key": key,
                                "value": value,
                                "category": fname.replace(".json", ""),
                                "source": self.name,
                            })
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Failed to read {path}: {e}")
                    continue
        return results


class UserNotesSource:
    """Read and write user-created notes."""

    def __init__(self, notes_dir):
        self.notes_dir = notes_dir
        self.name = "user_notes"
        self.reliability = 0.8
        os.makedirs(notes_dir, exist_ok=True)

    def get_all(self):
        """Get all user notes."""
        notes = {}
        notes_path = os.path.join(self.notes_dir, "notes.json")
        if os.path.exists(notes_path):
            try:
                with open(notes_path, "r", encoding="utf-8") as f:
                    notes = json.load(f)
            except json.JSONDecodeError:
                pass
        return notes

    def save_note(self, key, value):
        """Save a user note."""
        notes = self.get_all()
        notes[key] = {
            "value": value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        notes_path = os.path.join(self.notes_dir, "notes.json")
        with open(notes_path, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)
        return True

    def search(self, query):
        """Search user notes."""
        notes = self.get_all()
        results = []
        query_lower = query.lower()
        for key, data in notes.items():
            if query_lower in key.lower() or query_lower in data.get("value", "").lower():
                results.append({
                    "key": key,
                    "value": data["value"],
                    "source": self.name,
                    "timestamp": data.get("updated_at", ""),
                })
        return results
