from __future__ import annotations

import math
import re
from collections import Counter

from src.agent.state import PolicyChunk


TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_]+")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


class PolicyRetriever:
    def __init__(self, chunks: list[PolicyChunk]):
        self._chunks = chunks
        self._chunk_tokens = [_tokenize(f"{chunk.heading} {chunk.text}") for chunk in chunks]
        self._idf = self._build_idf(self._chunk_tokens)

    @staticmethod
    def _build_idf(tokenized_chunks: list[list[str]]) -> dict[str, float]:
        total_docs = len(tokenized_chunks) or 1
        document_frequencies: Counter[str] = Counter()
        for tokens in tokenized_chunks:
            document_frequencies.update(set(tokens))

        return {
            token: math.log((1 + total_docs) / (1 + freq)) + 1.0
            for token, freq in document_frequencies.items()
        }

    def search(self, query: str, top_k: int = 5) -> list[PolicyChunk]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        query_counts = Counter(query_tokens)
        scored: list[PolicyChunk] = []
        query_text = query.lower()

        for chunk, tokens in zip(self._chunks, self._chunk_tokens, strict=True):
            token_counts = Counter(tokens)
            score = 0.0
            for token, count in query_counts.items():
                score += count * token_counts.get(token, 0) * self._idf.get(token, 1.0)

            heading_tokens = set(_tokenize(chunk.heading))
            heading_overlap = heading_tokens.intersection(query_counts)
            if heading_overlap:
                score += sum(self._idf.get(token, 1.0) * 2.0 for token in heading_overlap)

            if query_text in chunk.text.lower():
                score += 3.0
            if any(token in chunk.heading.lower() for token in query_tokens):
                score += 1.5

            if score <= 0:
                continue

            scored.append(chunk.model_copy(update={"score": round(score, 4)}))

        scored.sort(key=lambda chunk: chunk.score or 0.0, reverse=True)
        return scored[:top_k]
