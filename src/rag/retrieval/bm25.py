"""코드 이름을 잘게 나누는 BM25 (외부 의존성 없음).

토큰화: ChatOpenAI → chatopenai, chat, open, ai / langchain.chains → langchain, chains
원래 이름(소문자)도 함께 남겨서 정확한 클래스 이름이 가장 강하게 맞도록 한다.
"""

import math
import re
from collections import Counter, defaultdict

from . import BM25_B, BM25_K1

WORD = re.compile(r"[A-Za-z0-9]+")
CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")
STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "for", "on", "with", "as", "by", "be", "it", "this", "that"}


def tokenize(text: str) -> list[str]:
    tokens = []
    for word in WORD.findall(text):
        lower = word.lower()
        parts = [p.lower() for p in CAMEL.findall(word)]
        if lower not in STOPWORDS:
            tokens.append(lower)
        if len(parts) > 1:
            tokens.extend(p for p in parts if len(p) > 1 and p not in STOPWORDS)
    return tokens


class BM25:
    def __init__(self, texts: list[str]):
        self.doc_len = []
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, text in enumerate(texts):
            counts = Counter(tokenize(text))
            self.doc_len.append(sum(counts.values()))
            for term, tf in counts.items():
                self.postings[term].append((i, tf))
        self.n = len(texts)
        self.avg_len = sum(self.doc_len) / max(self.n, 1)

    def idf(self, term: str) -> float:
        df = len(self.postings.get(term, ()))
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def scores(self, query: str, only: set[int] | None = None) -> dict[int, float]:
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokenize(query)):
            idf = self.idf(term)
            for i, tf in self.postings.get(term, ()):
                if only is not None and i not in only:
                    continue
                norm = tf + BM25_K1 * (1 - BM25_B + BM25_B * self.doc_len[i] / self.avg_len)
                scores[i] += idf * tf * (BM25_K1 + 1) / norm
        return scores

    def search(self, query: str, k: int, only: set[int] | None = None) -> list[tuple[int, float]]:
        return sorted(self.scores(query, only).items(), key=lambda x: -x[1])[:k]
