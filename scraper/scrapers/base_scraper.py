from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable


class BaseScraper(ABC):
    """Абстрактный класс для скрейпинга структурированных данных в CSV."""

    site_name = "generic"
    default_search_base_url = ""
    fieldnames: list[str] = []
    search_result_fieldnames: list[str] = []

    @abstractmethod
    def scrape(self, url: str | None = None, html: str | None = None) -> list[dict[str, str]]:
        """Возвращает список словарей с полями, определёнными в `fieldnames`."""

    def save_to_csv(
        self,
        rows: Iterable[dict[str, str]],
        output_filename: str,
        dedupe_key: str = "source_listing_id",
    ) -> None:
        self.save_rows_to_csv(
            rows=rows,
            output_filename=output_filename,
            fieldnames=self.fieldnames,
            dedupe_key=dedupe_key,
        )

    def save_rows_to_csv(
        self,
        rows: Iterable[dict[str, str]],
        output_filename: str,
        fieldnames: list[str],
        dedupe_key: str | None = None,
    ) -> None:
        rows = [self._normalize_row(row, fieldnames) for row in rows]
        if not rows:
            print("Нет данных для сохранения.")
            return

        output_path = Path(output_filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        stored_rows: list[dict[str, str]] = []
        row_index_by_key: dict[str, int] = {}

        if output_path.exists():
            with output_path.open("r", newline="", encoding="utf-8-sig") as csvfile:
                reader = csv.DictReader(csvfile)
                for index, existing_row in enumerate(reader):
                    normalized = self._normalize_row(existing_row, fieldnames)
                    stored_rows.append(normalized)
                    existing_key = normalized.get(dedupe_key, "") if dedupe_key else ""
                    if dedupe_key and existing_key:
                        row_index_by_key[existing_key] = index

        for row in rows:
            row_key = row.get(dedupe_key, "") if dedupe_key else ""
            if dedupe_key and row_key and row_key in row_index_by_key:
                stored_rows[row_index_by_key[row_key]] = row
            else:
                if dedupe_key and row_key:
                    row_index_by_key[row_key] = len(stored_rows)
                stored_rows.append(row)

        with output_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in stored_rows:
                writer.writerow(row)

    def _normalize_row(self, row: dict[str, str], fieldnames: list[str] | None = None) -> dict[str, str]:
        target_fields = fieldnames or self.fieldnames
        normalized: dict[str, str] = {}
        for field in target_fields:
            value = row.get(field, "")
            normalized[field] = "" if value is None else str(value)
        return normalized
