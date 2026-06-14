from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from src.agent.state import PolicyChunk
from src.rag.loader import DEFAULT_DOCS_DIR, load_policy_chunks
from src.rag.retriever import PolicyRetriever


class PolicySearchInput(BaseModel):
    query: str
    top_k: int = 5


class PolicySearchOutput(BaseModel):
    chunks: list[PolicyChunk] = Field(default_factory=list)


class PolicySearchTool:
    def __init__(self, documents_dir: Path = DEFAULT_DOCS_DIR):
        self.documents_dir = documents_dir
        self.retriever = PolicyRetriever(load_policy_chunks(documents_dir))

    def search_policy_docs(self, payload: PolicySearchInput) -> PolicySearchOutput:
        return PolicySearchOutput(chunks=self.retriever.search(payload.query, top_k=payload.top_k))
