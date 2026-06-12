"""
System configuration for the JARVIS Knowledge Engine.
"""
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG = {
    "version": "1.0.0",
    "name": "JARVIS Knowledge Engine",

    # Paths
    "knowledge_dir": os.path.join(BASE_DIR, "knowledge"),
    "memory_dir": os.path.join(BASE_DIR, "memory"),
    "cache_dir": os.path.join(BASE_DIR, "cache"),
    "sources_dir": os.path.join(BASE_DIR, "sources"),
    "logs_dir": os.path.join(BASE_DIR, "logs"),

    # Knowledge categories
    "categories": [
        "countries", "cities", "landmarks", "movies", "tv_shows",
        "games", "sports", "influencers", "technology", "ai",
        "history", "science", "food", "drinks", "religion",
        "culture", "geography", "treaties", "current_events",
        "music", "philosophy", "art", "nature", "people"
    ],

    # Source configuration
    "sources": {
        "wikipedia": {"enabled": True, "language": "en", "timeout": 10},
        "wikidata": {"enabled": True, "timeout": 10},
        "web_search": {"enabled": True, "timeout": 15},
        "news": {"enabled": True, "timeout": 10},
        "local_json": {"enabled": True},
        "local_text": {"enabled": True},
        "user_notes": {"enabled": True},
    },

    # Search settings
    "search": {
        "max_results": 10,
        "relevance_threshold": 0.3,
        "cache_ttl": 3600,  # seconds
        "async_requests": True,
    },

    # Learning settings
    "learning": {
        "confidence_threshold": 0.7,
        "require_verification": True,
        "max_sources_for_verification": 3,
        "auto_update_interval": 86400,  # seconds (24h)
    },

    # Memory settings
    "memory": {
        "max_memories_per_user": 1000,
        "memory_retention_days": 365,
        "summarize_after_messages": 50,
    },

    # Ranking
    "ranking": {
        "recency_weight": 0.3,
        "source_reliability_weight": 0.4,
        "relevance_weight": 0.3,
    },

    # Logging
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "file": os.path.join(BASE_DIR, "logs", "knowledge_engine.log"),
    },
}


def save_config(path=None):
    """Save current configuration to a JSON file."""
    path = path or os.path.join(BASE_DIR, "config", "config.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(CONFIG, f, indent=2)


def load_config(path=None):
    """Load configuration from a JSON file, merging with defaults."""
    path = path or os.path.join(BASE_DIR, "config", "config.json")
    if os.path.exists(path):
        with open(path) as f:
            loaded = json.load(f)
            CONFIG.update(loaded)
    return CONFIG
