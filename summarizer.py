import re
from collections import Counter

STOPWORDS = set("""
a an the and or but if of to in on at by for with from as is are was were be been
being this that these those it its he she they them his her their we our you your
i not no so than then there here have has had do does did will would can could
said says also into about over after before more most up out new one two
""".split())


def summarize(text, max_sentences=3):
    if not text:
        return "No article content could be extracted."

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    words = [w for w in re.findall(r"[a-z']+", text.lower()) if w not in STOPWORDS]
    freq = Counter(words)
    if not freq:
        return " ".join(sentences[:max_sentences])
    top = max(freq.values())

    scores = {}
    for i, s in enumerate(sentences):
        tokens = [w for w in re.findall(r"[a-z']+", s.lower()) if w not in STOPWORDS]
        if tokens:
            scores[i] = sum(freq[w] / top for w in tokens) / len(tokens) ** 0.5

    best = sorted(scores, key=scores.get, reverse=True)[:max_sentences]
    return " ".join(sentences[i] for i in sorted(best))