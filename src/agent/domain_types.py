from __future__ import annotations

import re
from typing import Literal


HousingType = Literal["apartment", "studio", "temporary_housing", "house"]


_HOUSING_TYPE_ALIASES: dict[HousingType, tuple[str, ...]] = {
    "apartment": (
        "apartment",
        "flat",
        "квартира",
        "квартиру",
        "квартире",
        "квартиры",
        "апартаменты",
        "апартаментов",
        "апартамент",
    ),
    "studio": (
        "studio",
        "студия",
        "студию",
        "студии",
    ),
    "temporary_housing": (
        "temporary housing",
        "temporary_housing",
        "short term",
        "short-term",
        "временное жилье",
        "временное жильё",
        "временное проживание",
    ),
    "house": (
        "house",
        "дом",
        "дома",
        "доме",
        "коттедж",
        "коттедже",
        "таунхаус",
    ),
}


def normalize_housing_type(raw: str | None) -> HousingType | None:
    if not raw:
        return None
    lowered = raw.strip().lower()
    for normalized, aliases in _HOUSING_TYPE_ALIASES.items():
        if lowered == normalized or lowered in aliases:
            return normalized
    return None


def infer_housing_type(text: str | None) -> HousingType | None:
    if not text:
        return None
    lowered = text.lower()
    for normalized, aliases in _HOUSING_TYPE_ALIASES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", lowered):
                return normalized
    return None
