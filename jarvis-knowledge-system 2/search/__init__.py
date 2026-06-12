class RankingPipeline:
    def __init__(self):
        pass

    def rank(self, results, query):
        q = query.lower()
        scored = []
        for r in results:
            score = 0
            key = r.get('key', '').lower()
            val = r.get('value', '').lower()
            if q == key:
                score += 100
            elif q in key:
                score += 50
            elif any(w in key for w in q.split()):
                score += 25
            if 'source' in r:
                if r['source'] == 'local':
                    score += 10
            scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored]

    def deduplicate(self, results):
        seen = set()
        unique = []
        for r in results:
            k = r.get('key', '')
            if k not in seen:
                seen.add(k)
                unique.append(r)
        return unique

    def format_answer(self, results, query):
        if not results:
            return None
        best = results[0]
        answer = best.get('value', '')
        source = best.get('source', 'unknown')
        url = best.get('url', '')
        if url:
            answer += f"\n\nSource: {url}"
        return answer

pipeline = RankingPipeline()
