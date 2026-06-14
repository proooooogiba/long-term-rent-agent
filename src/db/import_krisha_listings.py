from __future__ import annotations

import argparse
import csv
import sqlite3
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CSV_PATH = ROOT_DIR / "data" / "relocation" / "krisha_listings.csv"
DEFAULT_DB_PATH = ROOT_DIR / "data" / "relocation" / "krisha_normalized.sqlite"
PROTECTED_AGENT_DB_PATH = ROOT_DIR / "data" / "relocation" / "relocation.sqlite"
SCHEMA_PATH = Path(__file__).with_name("market_schema.sql")
KRISHA_SOURCE_ID = 1
COUNTRY_CODE = "KZ"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Импортирует krisha_listings.csv в нормализованную SQLite-схему."
    )
    parser.add_argument(
        "--csv-path",
        default=str(DEFAULT_CSV_PATH),
        help="Путь к CSV, собранному скрейпером Krisha.",
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="Путь к SQLite-базе с нормализованной схемой.",
    )
    return parser.parse_args()


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return int(float(cleaned))


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", ".")
    if not cleaned:
        return None
    return float(cleaned)


def _parse_bool(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    if cleaned == "true":
        return 1
    if cleaned == "false":
        return 0
    return None


def _posted_at_to_iso(value: str | None, fallback_iso: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return fallback_iso
    try:
        return datetime.fromisoformat(cleaned).replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return fallback_iso


def _infer_utilities_included(description: str | None) -> int | None:
    lowered = (description or "").lower()
    if not lowered:
        return None

    negative_markers = [
        "коммунальные услуги отдельно",
        "ком услуги отдельно",
        "комуслуги отдельно",
        "коммуналка отдельно",
        "аренда+ коммунальные услуги",
        "коммунальные отдельно",
    ]
    positive_markers = [
        "коммунальные услуги включены",
        "ком услуги включены",
        "комуслуги включены",
        "коммуналка включена",
    ]

    if any(marker in lowered for marker in negative_markers):
        return 0
    if any(marker in lowered for marker in positive_markers):
        return 1
    return None


def _median_or_none(values: list[int]) -> float | None:
    if not values:
        return None
    return float(round(statistics.median(values), 2))


def _build_city_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, str]]:
    unique_cities = sorted({(row.get("city") or "").strip() for row in rows if (row.get("city") or "").strip()})
    city_rows: list[dict[str, str]] = []
    city_id_by_name: dict[str, str] = {}

    for index, city_name in enumerate(unique_cities, start=1):
        city_id = f"CITY-{COUNTRY_CODE}-{index:03d}"
        city_id_by_name[city_name] = city_id
        city_rows.append(
            {
                "city_id": city_id,
                "country_code": COUNTRY_CODE,
                "name_ru": city_name,
            }
        )

    return city_rows, city_id_by_name


def _build_district_rows(
    rows: list[dict[str, str]],
    city_id_by_name: dict[str, str],
) -> tuple[list[dict[str, str]], dict[tuple[str, str], str]]:
    district_rows: list[dict[str, str]] = []
    district_id_by_key: dict[tuple[str, str], str] = {}

    grouped: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        city_name = (row.get("city") or "").strip()
        district_name = (row.get("district") or "").strip()
        if city_name and district_name:
            grouped[city_name].add(district_name)

    district_index = 1
    for city_name in sorted(grouped):
        city_id = city_id_by_name[city_name]
        for district_name in sorted(grouped[city_name]):
            district_id = f"DIST-{COUNTRY_CODE}-{district_index:04d}"
            district_index += 1
            district_rows.append(
                {
                    "district_id": district_id,
                    "city_id": city_id,
                    "name_ru": district_name,
                }
            )
            district_id_by_key[(city_name, district_name)] = district_id

    return district_rows, district_id_by_key


def _build_listing_rows(
    rows: list[dict[str, str]],
    city_id_by_name: dict[str, str],
    district_id_by_key: dict[tuple[str, str], str],
    import_timestamp_iso: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    listing_rows: list[dict[str, object]] = []
    price_rows: list[dict[str, object]] = []
    feature_rows: list[dict[str, object]] = []

    for row in rows:
        source_listing_id = (row.get("source_listing_id") or "").strip()
        city_name = (row.get("city") or "").strip()
        district_name = (row.get("district") or "").strip()
        if not source_listing_id or not city_name:
            continue

        city_id = city_id_by_name[city_name]
        district_id = district_id_by_key.get((city_name, district_name))
        listing_id = f"LIST-KRISHA-{source_listing_id}"

        listing_rows.append(
            {
                "listing_id": listing_id,
                "source_id": KRISHA_SOURCE_ID,
                "source_listing_id": source_listing_id,
                "city_id": city_id,
                "district_id": district_id,
                "url": (row.get("url") or "").strip(),
                "property_type": (row.get("property_type") or "").strip() or None,
                "rooms": _parse_int(row.get("rooms")),
                "area_m2": _parse_float(row.get("area_m2")),
                "floor": _parse_int(row.get("floor")),
                "floors_total": _parse_int(row.get("floors_total")),
                "furnished": (row.get("furnished") or "").strip() or None,
                "owner_type": (row.get("owner_type") or "").strip() or None,
                "description": (row.get("description") or "").strip(),
                "is_active": 1,
                "last_seen_at": _posted_at_to_iso(row.get("posted_at"), import_timestamp_iso),
            }
        )

        price_rows.append(
            {
                "listing_id": listing_id,
                "price_local": _parse_int(row.get("price_local")),
                "currency": (row.get("currency") or "").strip() or None,
                "deposit_local": _parse_int(row.get("deposit_local")),
                "utilities_included": _infer_utilities_included(row.get("description")),
                "captured_at": import_timestamp_iso,
            }
        )

        feature_rows.append(
            {
                "listing_id": listing_id,
                "elevator": _parse_bool(row.get("elevator")),
                "parking": _parse_bool(row.get("parking")),
                "balcony": _parse_bool(row.get("balcony")),
                "renovation": (row.get("renovation") or "").strip() or None,
                "pets_allowed": _parse_bool(row.get("pets_allowed")),
                "children_allowed": _parse_bool(row.get("children_allowed")),
            }
        )

    return listing_rows, price_rows, feature_rows


def _build_city_benchmarks(
    rows: list[dict[str, str]],
    city_id_by_name: dict[str, str],
    import_timestamp_iso: str,
) -> list[dict[str, object]]:
    city_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        city_name = (row.get("city") or "").strip()
        if city_name:
            city_groups[city_name].append(row)

    benchmark_rows: list[dict[str, object]] = []
    for city_name in sorted(city_groups):
        city_rows = city_groups[city_name]

        district_prices: dict[str, list[int]] = defaultdict(list)
        city_room_prices: dict[int, list[int]] = defaultdict(list)
        district_room_prices: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))

        for row in city_rows:
            district_name = (row.get("district") or "").strip() or "__unknown__"
            price = _parse_int(row.get("price_local"))
            rooms = _parse_int(row.get("rooms"))
            if price is None:
                continue

            district_prices[district_name].append(price)
            if rooms is not None:
                city_room_prices[rooms].append(price)
                district_room_prices[district_name][rooms].append(price)

        ordered_districts = sorted(
            district_prices.items(),
            key=lambda item: statistics.mean(item[1]),
            reverse=True,
        )

        center_count = max(1, round(len(ordered_districts) * 0.4)) if ordered_districts else 0
        center_districts = {name for name, _ in ordered_districts[:center_count]}
        outside_districts = {name for name, _ in ordered_districts[center_count:]}
        if not outside_districts:
            outside_districts = set(center_districts)

        def collect_prices(room_count: int, district_names: set[str]) -> list[int]:
            prices: list[int] = []
            for district_name in district_names:
                prices.extend(district_room_prices.get(district_name, {}).get(room_count, []))
            return prices

        def rent_estimate(room_count: int, district_names: set[str]) -> float | None:
            direct = collect_prices(room_count, district_names)
            if direct:
                return _median_or_none(direct)
            fallback = city_room_prices.get(room_count, [])
            if fallback:
                return _median_or_none(fallback)
            return None

        benchmark_rows.append(
            {
                "city_id": city_id_by_name[city_name],
                "source_name": "krisha_listings_csv_derived",
                "currency": "KZT",
                "cost_single_no_rent": None,
                "cost_family_no_rent": None,
                "rent_1br_center": rent_estimate(1, center_districts),
                "rent_1br_outside": rent_estimate(1, outside_districts),
                "rent_3br_center": rent_estimate(3, center_districts),
                "rent_3br_outside": rent_estimate(3, outside_districts),
                "updated_at": import_timestamp_iso,
            }
        )

    return benchmark_rows


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return list(csv.DictReader(csv_file))


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _assert_safe_target_db(db_path: Path) -> None:
    if db_path == PROTECTED_AGENT_DB_PATH.resolve():
        raise ValueError(
            "Нельзя импортировать в relocation.sqlite: этот файл занят рабочей схемой агента. "
            "Используй отдельную БД, например data/relocation/krisha_normalized.sqlite."
        )

    if not db_path.exists():
        return

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

    existing_tables = {row[0] for row in rows}
    protected_tables = {
        "clients",
        "client_preferences",
        "household_members",
        "relocation_cases",
        "relocation_services",
    }
    if existing_tables & protected_tables:
        raise ValueError(
            "Целевая БД похожа на рабочую БД агента. "
            "Для импорта Krisha нужен отдельный SQLite-файл."
        )


def _execute_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def _insert_rows(connection: sqlite3.Connection, rows: list[dict[str, object]]) -> dict[str, int]:
    connection.executemany(
        """
        INSERT INTO sources (source_id, name, base_url, country_code)
        VALUES (:source_id, :name, :base_url, :country_code)
        """,
        rows["sources"],
    )
    connection.executemany(
        """
        INSERT INTO cities (city_id, country_code, name_ru)
        VALUES (:city_id, :country_code, :name_ru)
        """,
        rows["cities"],
    )
    connection.executemany(
        """
        INSERT INTO districts (district_id, city_id, name_ru)
        VALUES (:district_id, :city_id, :name_ru)
        """,
        rows["districts"],
    )
    connection.executemany(
        """
        INSERT INTO listings (
            listing_id, source_id, source_listing_id, city_id, district_id, url,
            property_type, rooms, area_m2, floor, floors_total, furnished,
            owner_type, description, is_active, last_seen_at
        )
        VALUES (
            :listing_id, :source_id, :source_listing_id, :city_id, :district_id, :url,
            :property_type, :rooms, :area_m2, :floor, :floors_total, :furnished,
            :owner_type, :description, :is_active, :last_seen_at
        )
        """,
        rows["listings"],
    )
    connection.executemany(
        """
        INSERT INTO listing_prices (
            listing_id, price_local, currency, deposit_local, utilities_included, captured_at
        )
        VALUES (
            :listing_id, :price_local, :currency, :deposit_local, :utilities_included, :captured_at
        )
        """,
        rows["listing_prices"],
    )
    connection.executemany(
        """
        INSERT INTO listing_features (
            listing_id, elevator, parking, balcony, renovation, pets_allowed, children_allowed
        )
        VALUES (
            :listing_id, :elevator, :parking, :balcony, :renovation, :pets_allowed, :children_allowed
        )
        """,
        rows["listing_features"],
    )
    connection.executemany(
        """
        INSERT INTO city_cost_benchmarks (
            city_id, source_name, currency, cost_single_no_rent, cost_family_no_rent,
            rent_1br_center, rent_1br_outside, rent_3br_center, rent_3br_outside, updated_at
        )
        VALUES (
            :city_id, :source_name, :currency, :cost_single_no_rent, :cost_family_no_rent,
            :rent_1br_center, :rent_1br_outside, :rent_3br_center, :rent_3br_outside, :updated_at
        )
        """,
        rows["city_cost_benchmarks"],
    )
    connection.executemany(
        """
        INSERT INTO country_rules (
            country_code, internal_passport_entry_allowed, trp_summary, pr_summary,
            citizenship_summary, source_doc
        )
        VALUES (
            :country_code, :internal_passport_entry_allowed, :trp_summary, :pr_summary,
            :citizenship_summary, :source_doc
        )
        """,
        rows["country_rules"],
    )
    return {key: len(value) for key, value in rows.items()}


def main() -> None:
    args = _parse_args()
    csv_path = Path(args.csv_path).expanduser().resolve()
    db_path = Path(args.db_path).expanduser().resolve()

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV-файл не найден: {csv_path}")
    _assert_safe_target_db(db_path)

    csv_rows = _read_csv_rows(csv_path)
    import_timestamp_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    city_rows, city_id_by_name = _build_city_rows(csv_rows)
    district_rows, district_id_by_key = _build_district_rows(csv_rows, city_id_by_name)
    listing_rows, listing_price_rows, listing_feature_rows = _build_listing_rows(
        csv_rows,
        city_id_by_name,
        district_id_by_key,
        import_timestamp_iso,
    )
    city_benchmark_rows = _build_city_benchmarks(
        csv_rows,
        city_id_by_name,
        import_timestamp_iso,
    )

    payload = {
        "sources": [
            {
                "source_id": KRISHA_SOURCE_ID,
                "name": "Krisha",
                "base_url": "https://krisha.kz",
                "country_code": COUNTRY_CODE,
            }
        ],
        "cities": city_rows,
        "districts": district_rows,
        "listings": listing_rows,
        "listing_prices": listing_price_rows,
        "listing_features": listing_feature_rows,
        "city_cost_benchmarks": city_benchmark_rows,
        "country_rules": [
            {
                "country_code": COUNTRY_CODE,
                "internal_passport_entry_allowed": None,
                "trp_summary": None,
                "pr_summary": None,
                "citizenship_summary": None,
                "source_doc": "manual_fill_required: data/documents/07_cis_migration_basics.md",
            }
        ],
    }

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as connection:
        _execute_schema(connection)
        counts = _insert_rows(connection, payload)
        connection.commit()

    print(f"Импорт завершён: {db_path}")
    print(f"CSV строк: {len(csv_rows)}")
    for key in (
        "sources",
        "cities",
        "districts",
        "listings",
        "listing_prices",
        "listing_features",
        "city_cost_benchmarks",
        "country_rules",
    ):
        print(f"{key}: {counts[key]}")
    print("commute_targets: 0")
    print("listing_commute: 0")


if __name__ == "__main__":
    main()
