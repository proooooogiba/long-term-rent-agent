from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
WORKFLOW_OVERVIEW_PATH = ASSETS_DIR / "workflow_overview.svg"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.agent.graph import AgentSession, AgentTraceStep, AgentGraph, RelocationAgent
from src.agent.dependencies import GraphDependencies
from src.db.seed import DEFAULT_DB_PATH, seed_database
from src.runtime_config import (
    load_agent_runtime_config,
    resolve_llm_backend,
    resolve_llm_mode,
    resolve_openrouter_model,
)
from src.tools.relocation_db import RelocationDBTools


SUGGESTED_PROMPTS = [
    "Подбери 3 варианта аренды для текущего кейса.",
    "Объясни, какие риски есть у лучших вариантов.",
    "Какие районы ты бы рекомендовал и почему?",
    "Что изменится, если снизить бюджет на 15%?",
]


@st.cache_resource
def _ensure_database() -> str:
    return str(seed_database(DEFAULT_DB_PATH))


@st.cache_data
def _load_case_catalog(db_path_str: str) -> list[dict[str, object]]:
    with sqlite3.connect(db_path_str) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                rc.case_id,
                rc.client_id,
                rc.city,
                rc.country,
                rc.move_in_date,
                rc.monthly_budget,
                rc.upfront_budget,
                rc.max_commute_minutes,
                rc.document_status,
                rc.urgency_level,
                c.full_name
            FROM relocation_cases rc
            JOIN clients c ON c.client_id = rc.client_id
            ORDER BY rc.case_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _build_case_label(case: dict[str, object]) -> str:
    return (
        f"{case['case_id']} · {case['full_name']} · {case['city']} · "
        f"{float(case['monthly_budget']):.0f} USD"
    )


def _build_session(db_path_str: str) -> AgentSession:
    load_dotenv(ROOT_DIR / ".env")
    llm_mode = resolve_llm_mode("required")
    deps = GraphDependencies(
        db_tools=RelocationDBTools(Path(db_path_str)),
        llm_mode=llm_mode,
    )
    return AgentSession(agent=RelocationAgent(graph=AgentGraph(deps=deps)))


def _reset_conversation(db_path_str: str, case_id: str | None) -> None:
    st.session_state.agent_session = _build_session(db_path_str)
    st.session_state.messages = []
    st.session_state.selected_case_id = case_id


def _ensure_app_state(db_path_str: str) -> None:
    if "selected_case_id" not in st.session_state:
        st.session_state.selected_case_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent_session" not in st.session_state:
        _reset_conversation(db_path_str, st.session_state.selected_case_id)


def _inject_ui_styles() -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stMetricValue"] {
            font-size: 1.9rem;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.95rem;
        }
        .status-badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin: 8px 0 18px 0;
        }
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 8px 14px;
            border-radius: 999px;
            font-size: 0.95rem;
            font-weight: 600;
            line-height: 1.2;
        }
        .status-badge-label {
            opacity: 0.78;
        }
        .status-badge-value {
            font-weight: 700;
        }
        .status-badge.backend-live {
            color: #1d4ed8;
            background: #dbeafe;
            border: 1px solid #93c5fd;
        }
        .status-badge.backend-demo {
            color: #9a3412;
            background: #ffedd5;
            border: 1px solid #fdba74;
        }
        .status-badge.key-configured {
            color: #166534;
            background: #dcfce7;
            border: 1px solid #86efac;
        }
        .status-badge.key-missing {
            color: #991b1b;
            background: #fee2e2;
            border: 1px solid #fca5a5;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_case_sidebar(case: dict[str, object] | None) -> None:
    st.sidebar.subheader("Контекст")
    if case is None:
        st.sidebar.caption("Можно работать без готового кейса: агент сам извлечёт требования из сообщения.")
        return

    st.sidebar.markdown(f"**Кейс:** `{case['case_id']}`")
    st.sidebar.markdown(f"**Сотрудник:** {case['full_name']}")
    st.sidebar.markdown(f"**Город:** {case['city']}, {case['country']}")
    st.sidebar.markdown(f"**Переезд:** {case['move_in_date']}")
    st.sidebar.markdown(f"**Бюджет:** {float(case['monthly_budget']):.0f} USD/мес")
    st.sidebar.markdown(f"**Upfront budget:** {float(case['upfront_budget']):.0f} USD")
    st.sidebar.markdown(
        f"**Commute limit:** {case['max_commute_minutes']} мин · "
        f"**Docs:** {case['document_status']} · "
        f"**Urgency:** {case['urgency_level']}"
    )


def _render_suggested_prompts() -> None:
    columns = st.columns(len(SUGGESTED_PROMPTS))
    for column, prompt in zip(columns, SUGGESTED_PROMPTS):
        if column.button(prompt, key=f"prompt_{prompt}", width="stretch"):
            st.session_state["_pending_prompt"] = prompt


def _render_status_badges(llm_backend: str, configured_api_key: str | None) -> None:
    backend_class = "backend-demo" if llm_backend == "demo_stub" else "backend-live"
    key_configured = bool(configured_api_key)
    key_class = "key-configured" if key_configured else "key-missing"
    key_value = "configured" if key_configured else "missing"

    st.markdown(
        f"""
        <div class="status-badge-row">
            <div class="status-badge {backend_class}">
                <span class="status-badge-label">LLM backend</span>
                <span class="status-badge-value">{llm_backend}</span>
            </div>
            <div class="status-badge {key_class}">
                <span class="status-badge-label">OpenRouter key</span>
                <span class="status-badge-value">{key_value}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_messages(messages: list[dict[str, str]]) -> None:
    if not messages:
        st.info("Напишите запрос или выберите один из быстрых сценариев выше.")
        return

    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def _render_trace(trace_steps: list[AgentTraceStep]) -> None:
    if not trace_steps:
        st.info("После первого запроса здесь появится трассировка узлов графа.")
        return

    for index, step in enumerate(trace_steps, start=1):
        with st.expander(
            f"{index}. {step.title} · {step.duration_ms:.1f} ms",
            expanded=index == len(trace_steps),
        ):
            st.write(step.summary)


def _render_workflow_overview(_trace_steps: list[AgentTraceStep]) -> None:
    if WORKFLOW_OVERVIEW_PATH.exists():
        st.image(str(WORKFLOW_OVERVIEW_PATH), width="stretch")


def _render_state_snapshot(session: AgentSession) -> None:
    state = session.last_state
    if state is None:
        st.info("Состояние агента появится после первого ответа.")
        return

    metrics = st.columns(4)
    metrics[0].metric("Intent", state.intent or "—")
    metrics[1].metric(
        "Verifier",
        state.verification_result.status if state.verification_result else "—",
    )
    metrics[2].metric("Candidates", len(state.candidate_listings))
    metrics[3].metric("Ranked", len(state.ranked_listings))

    if state.requirements is not None:
        with st.expander("Извлечённые требования", expanded=True):
            st.json(state.requirements.model_dump(mode="json"))

    if state.persistent_memory_loaded:
        with st.expander("Persistent memory", expanded=False):
            st.markdown("**Источник:** внешний профиль кейса в SQLite")
            if state.persistent_memory_updated_at:
                st.markdown(f"**Последнее обновление:** {state.persistent_memory_updated_at}")
            if state.persistent_memory_summary:
                st.markdown(f"**Что было сохранено:** {state.persistent_memory_summary}")

    if state.changed_constraints:
        with st.expander("Изменённые ограничения", expanded=False):
            st.json(state.changed_constraints)

    if state.warnings or state.errors or state.missing_fields:
        with st.expander("Замечания и уточнения", expanded=False):
            if state.warnings:
                st.markdown("**Warnings**")
                for item in state.warnings:
                    st.write(f"- {item}")
            if state.missing_fields:
                st.markdown("**Missing fields**")
                for item in state.missing_fields:
                    st.write(f"- {item}")
            if state.errors:
                st.markdown("**Errors**")
                for item in state.errors:
                    st.write(f"- {item}")

    if state.retrieved_policy_chunks:
        with st.expander("RAG policy context", expanded=False):
            for chunk in state.retrieved_policy_chunks[:5]:
                st.markdown(f"**{chunk.heading}** · `{chunk.source}`")
                st.caption(chunk.text[:280] + ("..." if len(chunk.text) > 280 else ""))


def _render_shortlist(session: AgentSession) -> None:
    state = session.last_state
    if state is None or not state.ranked_listings:
        st.info("Шортлист появится, когда агент найдёт и оценит варианты.")
        return

    for rank, scored in enumerate(state.ranked_listings[:5], start=1):
        listing = scored.listing
        with st.expander(
            f"{rank}. {listing.title} · {listing.monthly_rent:.0f} {listing.currency}/мес",
            expanded=rank == 1,
        ):
            st.markdown(f"**ID:** `{listing.listing_id}`")
            st.markdown(
                f"**Район:** {listing.district_name} · "
                f"**Комнат:** {listing.rooms} · "
                f"**Площадь:** {listing.area_sqm:.0f} м²"
            )
            st.markdown(
                f"**Score:** {scored.total_score:.3f} · "
                f"**Upfront:** {scored.estimated_upfront_cost.total:.0f} {scored.estimated_upfront_cost.currency}"
            )
            if listing.commute_to_office_minutes is not None:
                st.markdown(f"**Commute to office:** {listing.commute_to_office_minutes} мин")
            if scored.pros:
                st.markdown("**Плюсы:** " + "; ".join(scored.pros))
            if scored.cons:
                st.markdown("**Компромиссы:** " + "; ".join(scored.cons))
            if scored.constraint_violations:
                st.markdown("**Нарушения ограничений:** " + ", ".join(scored.constraint_violations))


def _run_agent_turn(user_message: str, case_id: str | None) -> None:
    session: AgentSession = st.session_state.agent_session
    messages: list[dict[str, str]] = st.session_state.messages
    messages.append({"role": "user", "content": user_message})

    with st.status("Агент выполняет граф...", expanded=True) as status:
        try:
            state = session.handle_message(
                user_message,
                case_id=case_id,
                trace_callback=status.write,
            )
        except Exception as exc:
            status.update(label="Во время выполнения возникла ошибка", state="error", expanded=True)
            messages.append(
                {
                    "role": "assistant",
                    "content": f"Во время выполнения агента произошла ошибка: `{exc}`",
                }
            )
            st.exception(exc)
            return

        status.update(label="Агент завершил анализ", state="complete", expanded=False)
        messages.append(
            {
                "role": "assistant",
                "content": state.final_answer or "Агент не смог сформировать финальный ответ.",
            }
        )


def main() -> None:
    st.set_page_config(
        page_title="Relocation Agent",
        page_icon="🏠",
        layout="wide",
    )
    _inject_ui_styles()

    db_path_str = _ensure_database()

    try:
        _ensure_app_state(db_path_str)
    except ValueError as exc:
        st.error(
            "Не удалось инициализировать LLM. Проверьте `config/agent_runtime.json` "
            "или fallback-переменные `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `AGENT_LLM_MODE`."
        )
        st.code(str(exc))
        st.stop()

    cases = _load_case_catalog(db_path_str)
    case_map = {str(case["case_id"]): case for case in cases}
    case_options: list[str | None] = [None, *case_map.keys()]

    st.title("Агент подбора аренды и релокации")

    current_case_id = st.session_state.selected_case_id
    current_index = case_options.index(current_case_id) if current_case_id in case_options else 0
    selected_case_id = st.sidebar.selectbox(
        "Выберите кейс",
        options=case_options,
        index=current_index,
        format_func=lambda case_id: "Без готового кейса"
        if case_id is None
        else _build_case_label(case_map[case_id]),
    )

    if selected_case_id != current_case_id:
        try:
            _reset_conversation(db_path_str, selected_case_id)
        except ValueError as exc:
            st.error(
                "Не удалось пересоздать сессию с новым кейсом. Проверьте настройки LLM."
            )
            st.code(str(exc))
            st.stop()

    if st.sidebar.button("Сбросить диалог", width="stretch"):
        try:
            _reset_conversation(db_path_str, st.session_state.selected_case_id)
        except ValueError as exc:
            st.error("Не удалось сбросить диалог из-за ошибки инициализации LLM.")
            st.code(str(exc))
            st.stop()

    _render_case_sidebar(case_map.get(st.session_state.selected_case_id))

    runtime_config = load_agent_runtime_config()
    configured_api_key = (
        runtime_config.openrouter.api_key
        if runtime_config and runtime_config.openrouter.api_key
        else os.getenv("OPENROUTER_API_KEY")
    )
    llm_backend = (
        "demo_stub"
        if resolve_llm_backend("openrouter") == "demo_stub"
        else resolve_openrouter_model("deepseek/deepseek-v3.2")
    )

    _render_status_badges(llm_backend, configured_api_key)

    _render_suggested_prompts()
    pending_prompt = st.session_state.pop("_pending_prompt", None)
    user_input = st.chat_input("Опишите задачу или уточните ограничения...")
    new_message = user_input or pending_prompt

    if new_message:
        _run_agent_turn(new_message, st.session_state.selected_case_id)

    left_column, right_column = st.columns([1.3, 1.0], gap="large")

    with left_column:
        st.subheader("Диалог")
        _render_messages(st.session_state.messages)

    with right_column:
        st.subheader("Как работал агент")
        _render_workflow_overview(st.session_state.agent_session.last_trace)
        tabs = st.tabs(["Трассировка", "Состояние", "Шортлист"])
        with tabs[0]:
            _render_trace(st.session_state.agent_session.last_trace)
        with tabs[1]:
            _render_state_snapshot(st.session_state.agent_session)
        with tabs[2]:
            _render_shortlist(st.session_state.agent_session)


if __name__ == "__main__":
    main()
