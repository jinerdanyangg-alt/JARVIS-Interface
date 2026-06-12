import os
import json

class Config:
    def __init__(self, path=None):
        self.data_dir = path or os.path.join(os.path.dirname(__file__), '..', 'knowledge')
        self.data_dir = os.path.abspath(self.data_dir)
        self.sources = {
            'wiki': True,
            'wikidata': True,
            'web': True,
            'news': True,
            'local': True,
        }
        self.cache_ttl = 3600
        self.max_results = 5

    def get_knowledge_files(self):
        if not os.path.exists(self.data_dir):
            return []
        return [os.path.join(self.data_dir, f) for f in os.listdir(self.data_dir) if f.endswith('.json')]

    def load_all(self):
        data = {}
        for fp in self.get_knowledge_files():
            try:
                with open(fp, 'r') as f:
                    data.update(json.load(f))
            except (json.JSONDecodeError, IOError):
                pass
        return data

config = Config()
