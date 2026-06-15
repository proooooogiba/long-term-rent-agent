from __future__ import annotations

from typing import Final


USD_VALUE_BY_CURRENCY: Final[dict[str, float]] = {
    "USD": 1.0,
    "EUR": 1.08,
    "RUB": 1.0 / 90.0,
    "KZT": 1.0 / 460.0,
    "AMD": 1.0 / 390.0,
    "BYN": 1.0 / 3.2,
    "UZS": 1.0 / 12600.0,
}

_CURRENCY_ALIASES: Final[dict[str, str]] = {
    "$": "USD",
    "usd": "USD",
    "usdt": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "доллар": "USD",
    "доллара": "USD",
    "долларов": "USD",
    "евро": "EUR",
    "eur": "EUR",
    "€": "EUR",
    "rub": "RUB",
    "rur": "RUB",
    "₽": "RUB",
    "руб": "RUB",
    "рубль": "RUB",
    "рубля": "RUB",
    "рублей": "RUB",
    "kzt": "KZT",
    "₸": "KZT",
    "тенге": "KZT",
    "amd": "AMD",
    "֏": "AMD",
    "dram": "AMD",
    "драм": "AMD",
    "byn": "BYN",
    "белруб": "BYN",
    "uzs": "UZS",
    "сум": "UZS",
    "сумов": "UZS",
}


def normalize_currency_code(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in _CURRENCY_ALIASES:
        return _CURRENCY_ALIASES[normalized]
    upper = normalized.upper()
    return upper if upper in USD_VALUE_BY_CURRENCY else None


def convert_amount(amount: float | None, from_currency: str | None, to_currency: str | None) -> float | None:
    if amount is None:
        return None
    source = normalize_currency_code(from_currency)
    target = normalize_currency_code(to_currency)
    if source is None or target is None or source == target:
        return amount
    source_usd_value = USD_VALUE_BY_CURRENCY.get(source)
    target_usd_value = USD_VALUE_BY_CURRENCY.get(target)
    if source_usd_value is None or target_usd_value is None or target_usd_value == 0:
        return amount
    return round(amount * source_usd_value / target_usd_value, 2)
