import asyncio
import json
import os
import hashlib
import time

class Cache:
    def __init__(self, ttl=3600):
        self._store = {}
        self.ttl = ttl

    def get(self, key):
        entry = self._store.get(key)
        if entry and time.time() - entry['time'] < self.ttl:
            return entry['data']
        return None

    def set(self, key, data):
        self._store[key] = {'data': data, 'time': time.time()}

    def make_key(self, query):
        return hashlib.md5(query.encode()).hexdigest()

cache = Cache()

class LocalSource:
    def __init__(self, data_dir):
        self.data_dir = data_dir

    async def search(self, query):
        ck = cache.make_key('local:' + query)
        cached = cache.get(ck)
        if cached:
            return cached
        results = []
        q = query.lower()
        if os.path.exists(self.data_dir):
            for fname in os.listdir(self.data_dir):
                if fname.endswith('.json'):
                    fp = os.path.join(self.data_dir, fname)
                    try:
                        with open(fp, 'r') as f:
                            data = json.load(f)
                        for key, val in data.items():
                            if q in key.lower() or any(w in key.lower() for w in q.split()):
                                results.append({'key': key, 'value': val, 'source': 'local'})
                    except (json.JSONDecodeError, IOError):
                        pass
        cache.set(ck, results)
        return results

class WikipediaSource:
    def __init__(self):
        self.session = None

    async def search(self, query):
        ck = cache.make_key('wiki:' + query)
        cached = cache.get(ck)
        if cached:
            return cached
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = [{'key': query, 'value': data.get('extract', ''), 'source': 'wikipedia', 'url': data.get('content_urls', {}).get('desktop', {}).get('page', '')}]
                        cache.set(ck, result)
                        return result
        except ImportError:
            pass
        except Exception:
            pass
        return []

class WebSource:
    async def search(self, query):
        return []

class NewsSource:
    async def search(self, query):
        return []

async def search_all(query, sources):
    tasks = []
    for src in sources:
        if hasattr(src, 'search'):
            tasks.append(src.search(query))
    results = []
    for coro in asyncio.as_completed(tasks):
        try:
            results.extend(await coro)
        except Exception:
            pass
    return results
