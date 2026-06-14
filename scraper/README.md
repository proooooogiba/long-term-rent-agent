# Скрейпер объявлений аренды

Пакет `scraper/` собирает живые объявления аренды с `Krisha` и `List.am` и сохраняет их в CSV. Это не синтетические данные.

Основной код:

- `main.py` — CLI-точка входа
- `scrapers/krisha/krisha_scraper.py` — логика обхода выдачи и парсинга карточек `Krisha`
- `scrapers/list_am/list_am_scraper.py` — логика парсинга карточек и выдачи `List.am`

Что умеет:

- парсить одну карточку объявления;
- обходить поисковую выдачу по нескольким страницам;
- сохранять или обновлять общий CSV по `source_listing_id`;
- парсить локально сохранённые HTML-файлы карточек и выдачи через один параметр `--html-file`;
- для `Krisha` при нестабильной desktop-выдаче пробовать fallback на `m.krisha.kz`.

## Примеры запуска

Одна карточка `Krisha`:

```bash
python3 -m scraper.main --url "https://krisha.kz/a/show/1007937834"
```

Одна карточка `List.am` из сохранённого HTML:

```bash
python3 -m scraper.main --html-file "/path/to/listam_item.html"
```

Сбор датасета из выдачи `Krisha`:

```bash
python3 -m scraper.main \
  --search-url "https://krisha.kz/arenda/kvartiry/" \
  --pages 100 \
  --delay-sec 0.3 \
  --output "data/relocation/krisha_listings.csv"
```

Если нужно отдельно сохранить список найденных ссылок:

```bash
python3 -m scraper.main \
  --search-url "https://krisha.kz/arenda/kvartiry/" \
  --pages 100 \
  --delay-sec 0.3 \
  --links-output "data/relocation/krisha_listing_links.csv" \
  --output "data/relocation/krisha_listings.csv"
```

Разбор локально сохранённой выдачи `List.am`:

```bash
python3 -m scraper.main \
  --html-file "/path/to/listam_search_page.html" \
  --links-output "data/relocation/listam_listing_links.csv" \
  --output "data/relocation/listam_listings.csv"
```

Если сайт начинает часто отдавать таймауты, удобнее собирать датасет кусками:

```bash
python3 -m scraper.main \
  --search-url "https://krisha.kz/arenda/kvartiry/" \
  --start-page 11 \
  --pages 10 \
  --delay-sec 0.5 \
  --output "data/relocation/krisha_listings.csv"
```

Для `List.am` прямой HTTP-запрос к карточкам и выдаче может отдавать anti-bot страницу вместо данных. В таком случае для стабильного парсинга используй локально сохранённый HTML через тот же `--html-file`: скрейпер сам определит, что это карточка или выдача.

## Дополнительно

- [SUPPORTED_LINKS.md](./SUPPORTED_LINKS.md) — поддерживаемые URL и режимы
- [DEPENDENCIES.md](./DEPENDENCIES.md) — зависимости и установка
