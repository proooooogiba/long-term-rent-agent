# Агент подбора аренды жилья и релокации

Учебный E2E-проект по агентам: relocation assistant, который помогает подобрать аренду, объясняет ограничения кейса, умеет перестраивать рекомендации и аккуратно эскалирует рискованные запросы.

Под капотом здесь orchestration через state graph, typed tool layer, RAG по policy-документам, deterministic scoring, verifier/guardrails и replanning loop.

## Базовые фичи проекта

- подбор аренды по городу, бюджету, сроку переезда, составу семьи, питомцам, меблировке и commute;
- расчёт стартовых расходов: первый месяц, депозит, комиссия и move-in fees;
- объяснение, почему вариант подходит или не подходит;
- ответы на info-вопросы по районам, коммунальным, депозитам и базовым relocation policy;
- replanning shortlist при изменении бюджета, даты, города или ограничений;
- clarification, если не хватает данных для безопасной рекомендации;
- escalation для кейсов, где автоматический ответ может быть рискованным.

## How to start

1. Создайте виртуальное окружение и установите зависимости:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Подготовьте конфиг:

Для запуска с live LLM:

```bash
cp .env.example .env
cp config/agent_runtime.example.json config/agent_runtime.json
```

После этого укажите реальный `OPENROUTER_API_KEY` в `.env` или замените `openrouter.api_key` в `config/agent_runtime.json`.

Для воспроизводимого demo без внешней LLM:

```bash
cp config/agent_runtime.demo.example.json config/agent_runtime.json
```

3. Создайте или пересоздайте локальную БД:

```bash
python3 -m src.db.seed
```

4. Запустите интерфейс или CLI:

```bash
python3 -m src.app
```

или

```bash
streamlit run app.py
```

CLI-режим:

```bash
python3 -m src.app --cli
```

5. При необходимости прогоните проверки:

```bash
pytest
python3 -m src.evals.run_qa
python3 -m src.evals.run_qa --enforce-gate
```

## Быстрые команды

CLI:

- `/case R-0001` — загрузить кейс и начать диалог в его контексте;
- `/show` — показать текущий контекст;
- `/reset` — очистить сессию.

Streamlit:

- выбор relocation case из sidebar;
- чат с агентом и быстрые промпты;
- экран `Как работал агент` с трассировкой pipeline;
- shortlist и текущее состояние агента в отдельных вкладках.

## Документация

Полное оглавление материалов: [docs/README.md](docs/README.md)

Куда смотреть чаще всего:

- обзор проекта и детали архитектуры: [docs/project_overview.md](docs/project_overview.md)
- demo-сценарии и скриншоты: [docs/demo_scenarios.md](docs/demo_scenarios.md)
- схема и разбор оценки: [docs/evaluation_framework.md](docs/evaluation_framework.md)
- production operating notes: [docs/production_operating_model.md](docs/production_operating_model.md)
