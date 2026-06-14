from __future__ import annotations

from pathlib import Path

from src.tools.policy_search import PolicySearchInput, PolicySearchTool


def test_policy_search_prioritizes_matching_country_heading():
    documents_dir = Path(__file__).resolve().parents[1] / "data" / "documents"
    tool = PolicySearchTool(documents_dir)

    result = tool.search_policy_docs(PolicySearchInput(query="Армения гражданство ВНЖ", top_k=1))

    assert result.chunks
    assert "Армения" in result.chunks[0].heading
    assert result.chunks[0].source == "07_cis_migration_basics.md"
