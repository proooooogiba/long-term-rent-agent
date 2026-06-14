# MCP-ready adapters

Проект уже отделяет graph orchestration от tool layer, поэтому локальные адаптеры можно заменить MCP-серверами без переписывания узлов графа.

## Планируемые серверы

### `mcp-relocation-db`

Инструменты:

- `get_client_profile`
- `get_relocation_case`
- `search_listings`
- `get_listing`
- `get_district_info`
- `search_districts`
- `get_city_info`
- `get_country_profile`

### `mcp-rental-policy`

Инструменты:

- `search_policy_docs`
- `get_policy_section`

### `mcp-calculations`

Инструменты:

- `estimate_upfront_cost`
- `score_listing`
- `compare_listings`

## Как подключить вместо локального tool layer

1. Оставить интерфейс `GraphDependencies` неизменным.
2. Заменить `RelocationDBTools`, `PolicySearchTool`, `CalculationTools` на MCP-клиентские адаптеры с теми же typed-методами.
3. Узлы `router/intake/search/scoring/verifier` продолжат работать без изменений, потому что они общаются только с абстракцией tools.

## Статус в этом репозитории

- Локальные adapters полностью рабочие.
- Ниже лежат простые серверные заготовки с optional import `mcp.server.fastmcp`.
- Если MCP SDK не установлен, локальный режим продолжает работать без ограничений.
