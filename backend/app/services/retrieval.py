"""Small in-memory BM25 retriever for RAG. Unicode-safe for Hindi/Kannada (combining marks stay in the word)."""
import math
import re
from collections import Counter

_SPLIT = re.compile(r"""[^\s.,;:!?()\[\]{}"'“”‘’<>/\\|\-–—।]+""")


def tokenize(text: str) -> list[str]:
    return _SPLIT.findall((text or "").lower())


class BM25:
    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [tokenize(d) for d in documents]
        self.tf = [Counter(d) for d in self.docs]
        self.avgdl = (sum(len(d) for d in self.docs) / len(self.docs)) if self.docs else 0.0
        df: Counter = Counter()
        for d in self.tf:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, k: int = 5) -> list[tuple[int, float]]:
        q = tokenize(query)
        scored = []
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i]) or 1
            s = 0.0
            for t in q:
                f = tf.get(t, 0)
                if f:
                    s += self.idf.get(t, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1)))
            if s > 0:
                scored.append((i, s))
        return sorted(scored, key=lambda x: -x[1])[:k]
