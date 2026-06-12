"""
Search pipeline: orchestrates multi-source search, ranking, and answer generation.

Flow:
  User Question
  → Memory Search (past conversations)
  → Knowledge Base Search (local JSON)
  → Wikipedia/Wikidata Search (async)
  → Web Search (async)
  → News Search (async)
  → Source Ranking & Deduplication
  → Answer Generation with Citations
"""

import asyncio
import logging
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger("jarvis.search")


class SearchResult:
    """Represents a single search result from any source."""

    def __init__(self, content, source, title="", url="",
                 relevance=0.5, reliability=0.5, timestamp=None):
        self.content = content
        self.source = source
        self.title = title
        self.url = url
        self.relevance = relevance
        self.reliability = reliability
        self.timestamp = timestamp or datetime.now().isoformat()

    def score(self, recency_weight=0.3, rel_weight=0.4, reliability_weight=0.4):
        """Calculate combined score for ranking."""
        base = (self.relevance * rel_weight +
                self.reliability * reliability_weight)
        # Recency bonus: newer is better (within last 30 days)
        try:
            age = (datetime.now() - datetime.fromisoformat(self.timestamp)).days
            recency_score = max(0, 1 - age / 30) * recency_weight
        except (ValueError, TypeError):
            recency_score = 0
        return base + recency_score

    def to_dict(self):
        return {
            "content": self.content,
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "relevance": self.relevance,
            "reliability": self.reliability,
            "score": self.score(),
        }


class SearchPipeline:
    """Orchestrates parallel search across all sources and ranks results."""

    def __init__(self, knowledge_core, sources_module, memory_system, config):
        self.knowledge = knowledge_core
        self.sources = sources_module
        self.memory = memory_system
        self.config = config
        self.search_config = config.get("search", {})
        self.rank_config = config.get("ranking", {})

    async def search_all(self, query, user_id=None):
        """Execute search across all sources in parallel.

        Args:
            query: The search query
            user_id: Optional user ID for memory lookup

        Returns:
            Ranked list of SearchResult objects
        """
        results = []

        # 1. Memory search (synchronous)
        if user_id:
            memories = self.memory.search(query, user_id)
            for m in memories:
                results.append(SearchResult(
                    content=m.get("content", ""),
                    source="memory",
                    title=m.get("title", "Previous conversation"),
                    relevance=0.4 if m.get("type") == "preference" else 0.3,
                    reliability=0.9,
                    timestamp=m.get("timestamp", ""),
                ))

        # 2. Knowledge base search (synchronous)
        kb_results = self.knowledge.search_knowledge(query)
        for key, value, cat, score in kb_results:
            results.append(SearchResult(
                content=value,
                source="knowledge_base",
                title=key,
                relevance=score,
                reliability=0.95,
            ))

        # 3. Wikipedia (async)
        try:
            wiki_results = await self.sources.wikipedia.search(query)
            for r in wiki_results:
                results.append(SearchResult(
                    content=r.get("snippet", ""),
                    source="wikipedia",
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    relevance=0.7,
                    reliability=self.sources.wikipedia.reliability,
                ))
        except Exception as e:
            logger.warning(f"Wikipedia search failed: {e}")

        # 4. Wikidata (async)
        try:
            wd_results = await self.sources.wikidata.search(query)
            for r in wd_results:
                results.append(SearchResult(
                    content=r.get("description", ""),
                    source="wikidata",
                    title=r.get("label", ""),
                    url=r.get("url", ""),
                    relevance=0.6,
                    reliability=self.sources.wikidata.reliability,
                ))
        except Exception as e:
            logger.warning(f"Wikidata search failed: {e}")

        # 5. Web search (async)
        try:
            web_results = await self.sources.web.search(query)
            for r in web_results:
                results.append(SearchResult(
                    content=r.get("snippet", ""),
                    source="web",
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    relevance=0.5,
                    reliability=self.sources.web.reliability,
                ))
        except Exception as e:
            logger.warning(f"Web search failed: {e}")

        # 6. News (async)
        try:
            news_results = await self.sources.news.search(query)
            for r in news_results:
                results.append(SearchResult(
                    content=r.get("snippet", ""),
                    source="news",
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    relevance=0.5,
                    reliability=self.sources.news.reliability,
                    timestamp=datetime.now().isoformat(),
                ))
        except Exception as e:
            logger.warning(f"News search failed: {e}")

        # Rank and deduplicate
        ranked = self._rank_and_deduplicate(results)

        logger.info(f"Search for '{query}' returned {len(ranked)} results from {len(results)} raw hits")
        return ranked

    def _rank_and_deduplicate(self, results):
        """Rank results by combined score and remove near-duplicates."""
        for r in results:
            r.relevance = self._calculate_relevance(r)

        # Sort by score
        results.sort(key=lambda r: r.score(
            self.rank_config.get("recency_weight", 0.3),
            self.rank_config.get("relevance_weight", 0.4),
            self.rank_config.get("source_reliability_weight", 0.4),
        ), reverse=True)

        # Deduplicate: remove results with very similar content
        seen = set()
        deduped = []
        for r in results:
            # Use first 100 chars as fingerprint
            fingerprint = r.content[:100].lower()
            if fingerprint not in seen:
                seen.add(fingerprint)
                deduped.append(r)

        return deduped

    def _calculate_relevance(self, result):
        """Calculate relevance score with basic NLP heuristics."""
        return result.relevance  # Pass through for now, could use TF-IDF

    def format_answer(self, results, max_sources=3):
        """Format search results into a coherent answer with citations."""
        if not results:
            return {"answer": None, "sources": []}

        # Use top result content primarily
        primary = results[0]

        # Combine secondary sources for enrichment
        enrichment = ""
        for r in results[1:3]:
            if r.content and r.content not in primary.content:
                enrichment += " " + r.content

        answer = primary.content
        if enrichment:
            answer += enrichment

        # Collect citations
        citations = []
        seen_sources = set()
        for r in results[:max_sources]:
            source_name = r.source
            if r.title:
                display = f"{r.title} ({source_name})"
            else:
                display = f"Source: {source_name}"
            if display not in seen_sources:
                seen_sources.add(display)
                citations.append({
                    "title": r.title,
                    "source": r.source,
                    "url": r.url,
                    "reliability": r.reliability,
                })

        return {"answer": answer.strip(), "sources": citations}

    def search_local_only(self, query):
        """Quick synchronous search of local knowledge only (no network)."""
        results = []

        # Knowledge base
        kb_results = self.knowledge.search_knowledge(query)
        for key, value, cat, score in kb_results:
            results.append(SearchResult(
                content=value,
                source="knowledge_base",
                title=key,
                relevance=score,
                reliability=0.95,
            ))

        # Local files
        local_results = self.sources.local.search(query)
        for r in local_results:
            results.append(SearchResult(
                content=r.get("value", ""),
                source="local_file",
                title=r.get("key", ""),
                relevance=0.5,
                reliability=0.9,
            ))

        # User notes
        note_results = self.sources.notes.search(query)
        for r in note_results:
            results.append(SearchResult(
                content=r.get("value", ""),
                source="user_notes",
                title=r.get("key", ""),
                relevance=0.6,
                reliability=0.8,
                timestamp=r.get("timestamp", ""),
            ))

        results.sort(key=lambda r: r.score(), reverse=True)
        return results
