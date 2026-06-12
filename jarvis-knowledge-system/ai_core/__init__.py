"""
Core knowledge engine: retrieval, ranking, and answer generation.
"""

import json
import os
import logging
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger("jarvis.knowledge")

# In-memory knowledge store
_knowledge_store = {}
_source_reliability = {}
_last_update = {}


def load_category(category, knowledge_dir):
    """Load a single category JSON file into memory."""
    path = os.path.join(knowledge_dir, f"{category}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def load_all(knowledge_dir, categories):
    """Load all knowledge categories into memory."""
    global _knowledge_store
    total = 0
    for cat in categories:
        data = load_category(cat, knowledge_dir)
        if data:
            _knowledge_store[cat] = data
            total += len(data)
            logger.info(f"Loaded {len(data)} entries for category '{cat}'")
    logger.info(f"Total knowledge entries loaded: {total}")
    return _knowledge_store


def search_knowledge(query, categories=None, max_results=10):
    """Search the in-memory knowledge store for relevant entries.

    Args:
        query: Search string
        categories: Optional list of categories to limit search
        max_results: Maximum results to return

    Returns:
        List of (entry_key, entry_value, category, score) tuples
    """
    results = []
    query_lower = query.lower()
    query_words = set(query_lower.split())

    cats = categories or list(_knowledge_store.keys())

    for cat in cats:
        if cat not in _knowledge_store:
            continue
        for key, value in _knowledge_store[cat].items():
            key_lower = key.lower()
            score = 0

            # Exact match
            if key_lower == query_lower:
                score = 1.0
            # Key is substring of query
            elif key_lower in query_lower:
                score = len(key_lower) / max(len(query_lower), 1) * 0.9
            # Query words found in key
            else:
                key_words = set(key_lower.split())
                overlap = len(query_words & key_words)
                if overlap > 0:
                    score = overlap / max(len(key_words), 1) * 0.7

            if score >= 0.3:
                results.append((key, value, cat, score))

    # Sort by score descending, prefer longer key matches for specificity
    results.sort(key=lambda r: (r[3], len(r[0])), reverse=True)
    return results[:max_results]


def get_knowledge(key, category=None):
    """Get a specific knowledge entry by key and optional category."""
    if category:
        return _knowledge_store.get(category, {}).get(key)
    for cat, entries in _knowledge_store.items():
        if key in entries:
            return entries[key]
    return None


def add_knowledge(key, value, category, source="user", confidence=0.5):
    """Add a new knowledge entry.

    Args:
        key: The lookup key
        value: The knowledge content
        category: Knowledge category
        source: Source identifier
        confidence: Confidence score (0-1)
    """
    if category not in _knowledge_store:
        _knowledge_store[category] = {}
    _knowledge_store[category][key] = value
    _source_reliability[key] = {"source": source, "confidence": confidence}
    _last_update[key] = datetime.now().isoformat()
    logger.info(f"Added knowledge: {category}/{key} (confidence: {confidence})")


def update_knowledge(key, value, category=None, source=None, confidence=None):
    """Update an existing knowledge entry."""
    found = False
    for cat in _knowledge_store:
        if key in _knowledge_store.get(cat, {}):
            _knowledge_store[cat][key] = value
            found = True
            break
    if not found and category:
        add_knowledge(key, value, category, source or "system", confidence or 0.5)
    _last_update[key] = datetime.now().isoformat()


def remove_knowledge(key, category=None):
    """Remove a knowledge entry."""
    if category and category in _knowledge_store:
        return _knowledge_store[category].pop(key, None)
    for cat in _knowledge_store:
        if key in _knowledge_store.get(cat, {}):
            return _knowledge_store[cat].pop(key, None)
    return None


def get_all_entries():
    """Get all knowledge entries across all categories."""
    entries = []
    for cat, data in _knowledge_store.items():
        for key, value in data.items():
            entries.append({
                "key": key,
                "value": value,
                "category": cat,
                "source": _source_reliability.get(key, {}).get("source", "unknown"),
                "confidence": _source_reliability.get(key, {}).get("confidence", 0.5),
                "last_updated": _last_update.get(key, "unknown"),
            })
    return entries


def save_knowledge(knowledge_dir):
    """Persist all knowledge to disk."""
    for cat, data in _knowledge_store.items():
        path = os.path.join(knowledge_dir, f"{cat}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(data)} entries to {path}")


def get_stats():
    """Get statistics about the knowledge store."""
    stats = {"total_entries": 0, "categories": {}}
    for cat, data in _knowledge_store.items():
        stats["categories"][cat] = len(data)
        stats["total_entries"] += len(data)
    return stats
