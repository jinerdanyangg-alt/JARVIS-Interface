import json
import os

class KnowledgeBase:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self._memory = {}

    def add(self, key, value):
        self._memory[key.lower()] = value
        return True

    def get(self, key):
        return self._memory.get(key.lower())

    def delete(self, key):
        return self._memory.pop(key.lower(), None) is not None

    def list_keys(self):
        return list(self._memory.keys())

    def save_to_file(self, filename):
        fp = os.path.join(self.data_dir, filename)
        with open(fp, 'w') as f:
            json.dump(self._memory, f, indent=2)
        return fp

    def load_from_file(self, filename):
        fp = os.path.join(self.data_dir, filename)
        if os.path.exists(fp):
            with open(fp, 'r') as f:
                self._memory.update(json.load(f))
            return True
        return False

    def search(self, query):
        q = query.lower()
        results = []
        for key, val in self._memory.items():
            if q in key or any(w in key for w in q.split()):
                results.append({'key': key, 'value': val, 'source': 'memory'})
        return results
