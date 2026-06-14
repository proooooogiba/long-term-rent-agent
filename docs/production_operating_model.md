# Production Contour и operating notes

Этот файл описывает не только текущий учебный прототип, но и целевой operating contour, в котором решение можно было бы безопасно запускать как внутренний сервис.

Связанная схема: [relocation_agent_production_contour.drawio](relocation_agent_production_contour.drawio)

## Что уже реализовано в прототипе

- Персистентная память кейса: `agent_case_memory` и `agent_run_history` в `SQLite`.
- Write-back в профиль: обновление `client_preferences` и заметок `relocation_cases.notes`.
- Fallback-поведение для внешних MCP-источников: при сбое provider не рушит граф, а возвращает runtime warning.
- Offline quality gate: `src/evals/quality_gate.py` и `src/evals/run_qa.py --enforce-gate`.

## Что эта схема означает

- `API / Gateway` отвечает за входящий трафик, сессии и rate limit.
- `Agent Service` содержит orchestration graph и business guardrails.
- `Tool Layer` изолирует БД, RAG, расчёты и внешние MCP-provider adapters.
- `Case Profile + Persistent Memory` хранит не только текущее состояние кейса, но и write-back после каждого запуска.
- `Refresh Jobs` отвечают за импорт рыночных данных, нормализацию и контроль свежести.
- `Auth + Secrets` и `Observability` показаны отдельно, потому что это не логика агента, а обязательный production contour.

## Data freshness policy

Ниже зафиксирован целевой operating contract. Это важно для защиты, даже если часть SLA пока описана как target-state.

| Контур данных | Источник | Target freshness | Что считается просрочкой | Реакция |
|---|---|---|---|---|
| Case memory / write-back | `agent_case_memory`, `agent_run_history` | сразу после каждого agent run | нет записи по завершённому run | alert в logs + retry |
| Локальный каталог объявлений | импорт `Krisha` / `List.am` / batch market data | каждые 6 часов | старше 24 часов | warning в UI и alert оператору |
| Внешний live market lookup | hosted MCP provider (`Cian`) | on-demand на запрос | timeout или provider unavailable | fallback на локальные listings и runtime warning |
| Policy corpus / RAG | markdown policy docs | weekly review + внепланово при изменении правил | старше 14 дней без review для регуляторных разделов | content review task |
| QA metrics snapshot | `run_qa.py` | nightly и перед release/demo | последняя QA-сводка старше 24 часов | CI / release gate fail |

Принцип:

- live MCP полезен как источник свежих карточек и цен;
- локальная БД остаётся fallback-слоем и источником воспроизводимых demo/eval сценариев;
- policy/RAG данные не должны выглядеть “вечно актуальными”, поэтому у них есть отдельный review cadence.

## Auth и access control

Это target production design, а не текущая учебная реализация.

| Зона | Как должно работать |
|---|---|
| Пользовательский вход | SSO / corporate auth на уровне `API / Gateway` |
| Доступ к кейсам | RBAC по ролям `demo-viewer`, `relocation-operator`, `reviewer` |
| Секреты | токены `OpenRouter`, MCP provider credentials и service keys хранятся вне git, в secret store |
| Service-to-service auth | отдельные service credentials для MCP и LLM gateway |
| Audit trail | логируются `run_id`, `case_id`, `provider_id`, `intent`, `verifier_status`, но без утечки чувствительных данных |
| Human escalation | оператор видит только кейсы, назначенные его роли и очереди |

Минимальный security baseline для перехода из прототипа в pilot:

1. убрать секреты из локальных файлов и перенести их в vault/secret manager;
2. добавить SSO перед UI/API;
3. разделить права demo, operator и reviewer;
4. логировать вызовы внешних provider'ов и handoff-события.

## Observability

Набор минимальных production-сигналов:

| Категория | Что мерить |
|---|---|
| Latency | `agent_run_latency_ms`, `listing_search_latency_ms`, `mcp_provider_latency_ms` |
| Reliability | `mcp_provider_error_rate`, `empty_shortlist_rate`, `escalation_rate`, `clarification_rate` |
| Quality | offline QA metrics + quality gate status |
| Freshness | `market_data_age_hours`, `policy_corpus_review_age_days` |
| Product safety | доля кейсов с `escalation`, доля ответов без shortlist, доля handoff после document-risk |

Что писать в structured logs:

- `run_id`
- `case_id`
- `intent`
- `city`
- `provider_id`
- `candidate_count`
- `verifier_status`
- `quality_gate_passed` для batch QA

Рекомендуемые alert'ы:

- `mcp_provider_error_rate > 20%` за 15 минут
- `market_data_age_hours > 24`
- `empty_shortlist_rate > 30%` по search-кейсам
- `quality_gate_passed = false` на nightly QA

## Residual gap

На текущий момент production contour:

- описан;
- частично реализован в части persistent memory, write-back и eval gate;
- не реализован полностью в части SSO, secret manager и централизованной observability platform.
