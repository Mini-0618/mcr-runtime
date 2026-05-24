#!/usr/bin/env python3
with open('./layered_memory.py') as f:
    content = f.read()

old = '''        semantic_scored = []
        if self.semantic:
            for m in self.semantic:
                m = dict(m)
                gr = self._calc_goal_relevance(m, current_goal, goal_history, current_tick)
                m["goal_relevance"] = gr
                score = self._retrieval_score(m, query, current_goal, current_tick)
                m["retrieval_score"] = score
                semantic_scored.append(m)
            semantic_scored.sort(key=lambda x: x["retrieval_score"], reverse=True)'''

new = '''        semantic_scored = []
        if self.semantic:
            # Prefilter: cheap keyword overlap before expensive scoring
            query_words = set(query.lower().split()) if query else set()
            semantic_candidates = []
            for m in self.semantic:
                content_words = set(m.get("content", "").lower().split())
                if query_words and content_words and len(query_words & content_words) >= 1:
                    semantic_candidates.append(m)
            for m in semantic_candidates:
                m = dict(m)
                gr = self._calc_goal_relevance(m, current_goal, goal_history, current_tick)
                m["goal_relevance"] = gr
                score = self._retrieval_score(m, query, current_goal, current_tick)
                m["retrieval_score"] = score
                semantic_scored.append(m)
            semantic_scored.sort(key=lambda x: x["retrieval_score"], reverse=True)'''

if old in content:
    content = content.replace(old, new, 1)
    open('./layered_memory.py', 'w').write(content)
    print('PATCHED semantic prefilter')
else:
    print('NOT FOUND - searching...')
    idx = content.find("semantic_scored = []")
    print(repr(content[idx-50:idx+600]))
