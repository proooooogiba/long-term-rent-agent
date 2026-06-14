# Реальный внешний MCP provider: пример shortlist

## Что именно проверяли

- Provider: `Apify MCP`
- Actor / tool: `igolaizola/cian-ru-scraper`
- Дата capture: `2026-06-14`
- Query:
  - `location=Москва`
  - `maxPrice=120000`
  - `rooms=["1"]`
  - `operationType=rent`
  - `category=flatRent`

Важно:

- это не raw JSON ответа сайта, а уже нормализованный результат в общую доменную модель `Listing`;
- каждое объявление помечено `source:cian`, то есть попадает в тот же общий shortlist format, что и локальные listings.

## Top-3 после нормализации

| Rank | listing_id | Заголовок | Район / адрес | Цена | Комнаты | Площадь |
|---|---|---|---|---|---|---|
| 1 | `cian:330998771` | `Добрый Дом` | `улица Паперника, 15, Москва` | `25000 RUB` | `1` | `14.0 м²` |
| 2 | `cian:329995460` | `АРКАНА` | `Дмитровское шоссе, 107Б, Москва` | `38000 RUB` | `1` | `20.0 м²` |
| 3 | `cian:330992338` | `Москва` | `улица Гришина, 21К2, Москва` | `45000 RUB` | `1` | `32.0 м²` |

## Пример одной карточки в общем shortlist shape

```json
{
  "listing_id": "cian:330998771",
  "title": "Добрый Дом",
  "district_name": "улица Паперника, 15, Москва",
  "monthly_rent": 25000.0,
  "currency": "RUB",
  "rooms": 1,
  "area_sqm": 14.0,
  "available_from": "2026-06-11",
  "notes": [
    "source:cian",
    "url:https://www.cian.ru/rent/flat/330998771/?mlSearchSessionGuid=2aa6949d6e96cfb46d5171e9565b3743"
  ]
}
```

## Что пришлось сделать в адаптере

- подобрать правильный alias имени инструмента: hosted MCP возвращает `igolaizola--cian-ru-scraper`;
- убрать автоматическую отправку десятков `boolean=false` schema-default полей;
- добавить schema-aware coercion для `integer` аргументов;
- поддержать двухшаговый контракт `actor run -> get-dataset-items`;
- дообогатить нормализацию Cian-полей до общей модели `Listing`.

## Что это доказывает на защите

- проект умеет не только работать на локальной SQLite;
- внешний hosted MCP provider действительно подключён и проверен;
- live provider интегрирован не “рядом”, а в общий нормализованный shortlist format.
