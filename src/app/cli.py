from __future__ import annotations

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from src.agent.dependencies import GraphDependencies
from src.agent.graph import AgentGraph, AgentSession, RelocationAgent
from src.db.seed import DEFAULT_DB_PATH, seed_database
from src.runtime_config import resolve_llm_mode, resolve_openrouter_model
from src.tools.relocation_db import GetRelocationCaseInput, RelocationDBTools


console = Console()


def _case_summary(db: RelocationDBTools, case_id: str) -> str:
    case = db.get_relocation_case(GetRelocationCaseInput(case_id=case_id))
    if case is None:
        return f"Кейс {case_id} не найден."
    return (
        f"{case.case_id}: {case.city}, бюджет {case.monthly_budget:.0f} USD, "
        f"переезд {case.move_in_date.isoformat()}, commute до {case.max_commute_minutes or 'n/a'} минут."
    )


def _print_help() -> None:
    console.print(
        Panel.fit(
            "\n".join(
                [
                    "Команды:",
                    "/case R-0001  — загрузить кейс и сбросить сессию",
                    "/show  — показать текущий case_id и последний intent",
                    "/reset  — очистить диалоговую память",
                    "/quit  — выйти",
                ]
            ),
            title="Relocation Agent CLI",
        )
    )


def _build_session(db_path=DEFAULT_DB_PATH) -> AgentSession:
    load_dotenv()
    llm_mode = resolve_llm_mode("required")
    deps = GraphDependencies(
        db_tools=RelocationDBTools(db_path),
        llm_mode=llm_mode,
    )
    return AgentSession(agent=RelocationAgent(graph=AgentGraph(deps=deps)))


def main() -> None:
    seed_database(DEFAULT_DB_PATH)
    db = RelocationDBTools(DEFAULT_DB_PATH)
    session = _build_session(DEFAULT_DB_PATH)
    current_case_id: str | None = None

    console.print("[bold green]Relocation agent CLI ready.[/bold green]")
    console.print(f"[dim]LLM mode: {resolve_llm_mode('required')}[/dim]")
    console.print(f"[dim]Model: {resolve_openrouter_model('deepseek/deepseek-v3.2')}[/dim]")
    _print_help()

    while True:
        user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]").strip()
        if not user_input:
            continue

        if user_input in {"/quit", "/exit"}:
            break

        if user_input == "/help":
            _print_help()
            continue

        if user_input == "/reset":
            session = _build_session(DEFAULT_DB_PATH)
            current_case_id = None
            console.print("[yellow]Сессия сброшена.[/yellow]")
            continue

        if user_input == "/show":
            intent = session.last_state.intent if session.last_state else None
            console.print(f"case_id={current_case_id or '-'}; last_intent={intent or '-'}")
            continue

        if user_input.startswith("/case "):
            current_case_id = user_input.split(maxsplit=1)[1].strip()
            session = _build_session(DEFAULT_DB_PATH)
            console.print(f"[yellow]Контекст переключён:[/yellow] {_case_summary(db, current_case_id)}")
            continue

        state = session.handle_message(user_input, case_id=current_case_id)
        console.print(
            Panel(
                state.final_answer,
                title=f"Intent={state.intent} | Status={state.verification_result.status if state.verification_result else '-'}",
            )
        )


if __name__ == "__main__":
    main()
