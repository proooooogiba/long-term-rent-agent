# Зависимости пакета `scraper`

## Python

- Рекомендуемая версия: `Python 3.12+`

## Python-пакеты

Файл зависимостей:

- [requirements.txt](./requirements.txt)

Содержимое:

- `beautifulsoup4>=4.12,<5.0`
- `requests>=2.31,<3.0`

## Установка

Из корня проекта:

```bash
./.venv/bin/pip install -r scraper/requirements.txt
```

Если виртуальное окружение ещё не создано:

```bash
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r scraper/requirements.txt
```

## Системные зависимости

Отдельный браузер не нужен. Скрейпер работает через:

- `requests` для загрузки HTML;
- `BeautifulSoup` для разбора страницы;
- встроенные эвристики для извлечения данных из `window.data`, DOM и текста описания.

## Что используется в коде

- `requests`
  - загружает HTML страницы объявления `Krisha`
- `beautifulsoup4`
  - разбирает DOM и служебные блоки страницы
