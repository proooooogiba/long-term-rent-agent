# Поддерживаемые ссылки для скрейпера объявлений

Сейчас пакет поддерживает карточки и выдачу для двух источников:

1. `Krisha`
2. `List.am`

## Пример URL

`Krisha`:

- `https://krisha.kz/a/show/1007937834`
- `https://krisha.kz/arenda/kvartiry/`
- `https://m.krisha.kz/arenda/kvartiry/?rent-period-switch=%2Farenda%2Fkvartiry&page=2`

`List.am`:

- `https://www.list.am/en/item/23837753`
- `https://www.list.am/en/category/56`
- `https://www.list.am/en/category/56/2`

## Что делает программа

1. Принимает URL объявления, URL поисковой выдачи или локальный HTML-файл карточки/выдачи.
2. В режиме карточки извлекает структурированные поля объявления.
3. В режиме выдачи обходит `N` страниц, собирает ссылки на карточки и затем парсит сами объявления.
4. Создаёт или дополняет CSV.
5. При повторном запуске по тому же `source_listing_id` обновляет существующую запись, а не создаёт бесконечные дубли.
6. Если desktop-выдача `krisha.kz` отвечает нестабильно, скрейпер автоматически пробует ту же страницу на `m.krisha.kz`.
7. Локальный HTML передаётся всегда через `--html-file`: скрейпер сам определяет, карточка это или поисковая выдача.

## Формат выходного файла

По умолчанию данные сохраняются в:

- `data/relocation/krisha_listings.csv`
- `data/relocation/listam_listings.csv`

Можно передать свой путь через `--output`.

## Примеры запуска

Из корня проекта:

```bash
python3 -m scraper.main --url "https://krisha.kz/a/show/1007937834"
```

```bash
python3 -m scraper.main --html-file "/path/to/listam_item.html"
```

Для поисковой выдачи `Krisha` на 100 страниц:

```bash
python3 -m scraper.main \
  --search-url "https://krisha.kz/arenda/kvartiry/" \
  --pages 100 \
  --delay-sec 0.3 \
  --output "data/relocation/krisha_listings.csv"
```

Для более стабильного сбора можно идти партиями, например страницами `11-20`:

```bash
python3 -m scraper.main \
  --search-url "https://krisha.kz/arenda/kvartiry/" \
  --start-page 11 \
  --pages 10 \
  --delay-sec 0.5 \
  --output "data/relocation/krisha_listings.csv"
```

Если нужно отдельно сохранить список найденных ссылок:

```bash
python3 -m scraper.main \
  --search-url "https://krisha.kz/arenda/kvartiry/" \
  --pages 5 \
  --delay-sec 0.3 \
  --links-output "data/relocation/krisha_listing_links.csv"
```

Для длинных прогонов `--delay-sec` помогает снизить вероятность сетевых таймаутов и временных блокировок со стороны сайта.

Для локального HTML-файла:

```bash
python3 -m scraper.main --html-file "/path/to/page.html"
```

Для локально сохранённой выдачи `List.am`:

```bash
python3 -m scraper.main \
  --html-file "/path/to/listam_search_page.html" \
  --links-output "data/relocation/listam_listing_links.csv"
```

Если `List.am` отдаёт anti-bot страницу вместо HTML, используй офлайн-режим с сохранёнными страницами браузера.
