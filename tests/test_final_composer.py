from __future__ import annotations

import pytest

from src.agent.dependencies import GraphDependencies
from src.agent.final_composer import final_composer_node
from src.agent.state import AgentState, PolicyChunk, VerificationResult
from src.db.seed import seed_database
from src.tools.relocation_db import GetCountryProfileInput, RelocationDBTools


def test_info_answer_includes_reference_links(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    db_tools = RelocationDBTools(db_path)
    country_profile = db_tools.get_country_profile(GetCountryProfileInput(country="Армения"))

    deps = GraphDependencies(db_tools=db_tools, llm_mode="off")
    state = AgentState(
        user_message="Какие базовые правила по ВНЖ в Армении?",
        intent="info",
        country_profile=country_profile,
        retrieved_policy_chunks=[
            PolicyChunk(
                source="07_cis_migration_basics.md",
                heading="Армения: residence status и гражданство",
                text="Источники: https://migration.e-gov.am/en/service/residency_application/info",
            )
        ],
    )

    state = final_composer_node(state, deps)

    assert state.final_answer is not None
    assert "Источники:" in state.final_answer
    assert "https://migration.e-gov.am/en/service/residency_application/info" in state.final_answer


def test_clarification_answer_no_longer_uses_local_fallback(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    db_tools = RelocationDBTools(db_path)
    deps = GraphDependencies(db_tools=db_tools, llm_mode="off")
    state = AgentState(
        user_message="Подбери аренду, но деталей пока мало.",
        intent="clarification",
        missing_fields=["city"],
        verification_result=VerificationResult(
            status="clarification",
            required_user_clarifications=["в каком городе искать жильё"],
        ),
    )

    with pytest.raises(RuntimeError, match="Clarification answer composition requires a configured StructuredLLM"):
        final_composer_node(state, deps)
