# Разбор проекта по критериям оценивания

Этот файл оценивает проект по критериям из `Критерии для оценивания работ.md`.

Пункт `Качество представления информации` здесь намеренно не оценивается.

## 1. Агент / МАС соответствует критериям агентности

Статус: `закрыто уверенно для уровня учебного проекта`.

Что уже есть:

- роли разведены по узлам графа, а не сведены к одному общему prompt;
- есть reflection через `verifier` и `replanner`;
- есть session memory и persistent memory;
- реализован write-back во внешний профиль кейса через `agent_case_memory`, `agent_run_history`, `client_preferences`, `relocation_cases.notes`;
- есть action layer через typed tools, local DB tools и optional MCP providers.

Что осталось как развитие, а не как критичный gap:

- нет supervisor/sub-agent orchestration с динамическим созданием агентов;
- нет online learning из human feedback;
- нет автоматического подключения новых инструментов beyond preconfigured registry.

## 2. Описана архитектура решения и проект

Статус: `закрыто`.

Что теперь есть:

- верхнеуровневая архитектура в `drawio`;
- функциональный flow в `drawio`;
- отдельная production-contour схема;
- отдельный operating note про `data freshness`, `auth`, `observability`;
- описание persistent memory и write-back path.

Что важно честно проговорить на защите:

- production contour описан как target-state;
- SSO, vault и централизованная observability ещё не внедрены в код как полноценная инфраструктура.

## 3. Определены и описаны метрики качества работы агента

Статус: `закрыто, с честным quality gate`.

Что уже есть:

- offline QA metrics в `src/evals/metrics.py`;
- quality gate в `src/evals/quality_gate.py`;
- запуск `python3 -m src.evals.run_qa --enforce-gate`;
- целевые пороги для core QA metrics;
- разделение метрик на hard gate и soft gate.

Что важно показать:

- проект не только считает метрики, но и фиксирует минимально допустимый барьер качества;
- текущий `demo_stub` не проходит quality gate полностью, и это нормально: в материалах зафиксирован не только target, но и реальный текущий статус.

## 4. Прототип и техническая готовность решения

Статус: `закрыто сильнее, чем было изначально`.

Что теперь добавлено:

- `Streamlit`, `CLI`, `QA runner`, `pytest`;
- persistent memory с write-back;
- demo-сценарии со скриншотами для `search`, `replanning`, `escalation`;
- пример реального внешнего MCP provider в общем shortlist format;
- production-contour и operating notes как bridge от прототипа к pilot/production.

Что осталось как residual risk:

- hosted MCP provider может быть нестабилен как внешний сервис;
- live integration стоит показывать как bonus path, а не как единственный источник данных.

## 5. Описаны проблемы, ограничения и дальнейшее развитие

Статус: `закрыто`.

Что уже отражено:

- ограничения юридически чувствительных кейсов;
- ограничение на freshness рыночных данных;
- trade-off между воспроизводимостью и агентностью;
- staged путь от локальной SQLite к production services;
- конкретные следующие шаги по auth, observability и quality improvement.

## Итог

По сравнению с предыдущей версией проекта закрыты все пять практических gap'ов, которые сильнее всего мешали защите:

1. добавлена persistent memory / write-back;
2. добавлен production contour и operating notes;
3. зафиксированы QA thresholds и minimal quality gate;
4. подготовлены demo-сценарии с UI-скриншотами;
5. показан реальный внешний MCP provider с нормализованным shortlist example.

Главный честный остаточный gap теперь не в структуре проекта, а в глубине production-внедрения:

- auth / observability / secret management пока описаны как target-state;
- качество `demo_stub` ниже целевого gate по router/escalation/narrative метрикам;
- hosted MCP integration стоит считать рабочим, но внешне зависимым каналом.
