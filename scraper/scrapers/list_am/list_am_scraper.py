from __future__ import annotations

import re
from time import sleep
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

from scraper.scrapers.base_scraper import BaseScraper


class ListAmScraper(BaseScraper):
    site_name = "listam"
    default_search_base_url = "https://www.list.am/en/category/56"
    fieldnames = [
        "source_listing_id",
        "url",
        "city",
        "district",
        "address_text",
        "property_type",
        "rooms",
        "area_m2",
        "floor",
        "floors_total",
        "price_local",
        "currency",
        "deposit_local",
        "furnished",
        "owner_type",
        "elevator",
        "parking",
        "balcony",
        "renovation",
        "pets_allowed",
        "children_allowed",
        "description",
        "posted_at",
    ]
    search_result_fieldnames = [
        "page_number",
        "position",
        "source_listing_id",
        "listing_url",
        "title",
        "price_summary",
    ]

    request_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    connect_timeout_sec = 8
    read_timeout_sec = 15
    max_retries = 2
    known_attribute_labels = {
        "Floor Area",
        "Floor",
        "Floors in the Building",
        "Ceiling Height",
        "Number of Rooms",
        "Number of Bathrooms",
        "Construction Type",
        "New Construction",
        "Elevator",
        "Balcony",
        "Furniture",
        "Renovation",
        "Children Are Welcome",
        "Pets Allowed",
        "Utility Payments",
        "Prepayment",
        "Price",
    }

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(self.request_headers)
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        self.last_search_page_errors: list[dict[str, str]] = []

    def scrape(self, url: str | None = None, html: str | None = None) -> list[dict[str, str]]:
        if html is None:
            if not url:
                raise ValueError("Для загрузки страницы нужен URL.")
            html = self._fetch_html(url, request_kind="listing")

        return [self._parse_listing(html, source_url=url)]

    def collect_listing_links(
        self,
        search_url: str,
        pages: int = 1,
        start_page: int = 1,
        delay_sec: float = 0.0,
    ) -> list[dict[str, str]]:
        if pages < 1:
            raise ValueError("Количество страниц должно быть не меньше 1.")
        if start_page < 1:
            raise ValueError("Начальная страница должна быть не меньше 1.")

        all_rows: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        self.last_search_page_errors = []
        end_page = start_page + pages - 1

        for page_number in range(start_page, end_page + 1):
            page_url = self._build_search_page_url(search_url, page_number)
            print(f"Загружаю страницу выдачи {page_number}/{end_page}: {page_url}")

            try:
                response = self._fetch_response(
                    page_url,
                    request_kind="search",
                    context=f"страница выдачи {page_number}",
                )
            except Exception as exc:
                self.last_search_page_errors.append(
                    {
                        "page_number": str(page_number),
                        "page_url": page_url,
                        "error": str(exc),
                    }
                )
                raise

            page_rows = self.collect_listing_links_from_html(
                html=response.text,
                search_url=response.url,
                page_number=page_number,
            )
            if not page_rows:
                break

            for row in page_rows:
                row_id = row.get("source_listing_id", "")
                if row_id and row_id in seen_ids:
                    continue
                if row_id:
                    seen_ids.add(row_id)
                all_rows.append(row)

            if delay_sec > 0 and page_number < end_page:
                sleep(delay_sec)

        return all_rows

    def collect_listing_links_from_html(
        self,
        html: str,
        search_url: str | None = None,
        page_number: int = 1,
    ) -> list[dict[str, str]]:
        return self._extract_listing_links_from_search_html(
            html=html,
            search_url=search_url or self.default_search_base_url,
            page_number=page_number,
        )

    def save_search_results_to_csv(self, rows: list[dict[str, str]], output_filename: str) -> None:
        self.save_rows_to_csv(
            rows=rows,
            output_filename=output_filename,
            fieldnames=self.search_result_fieldnames,
            dedupe_key="source_listing_id",
        )

    def _fetch_html(self, url: str, request_kind: str = "listing") -> str:
        response = self._fetch_response(
            url,
            request_kind=request_kind,
            context=url,
        )
        return response.text

    def _fetch_response(
        self,
        url: str,
        request_kind: str = "listing",
        context: str | None = None,
    ) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._session.get(
                    url,
                    timeout=(self.connect_timeout_sec, self.read_timeout_sec),
                )
                response.encoding = response.encoding or "utf-8"

                if self._is_block_page(response.text):
                    raise RuntimeError(
                        self._build_blocked_error_message(
                            request_kind=request_kind,
                            url=url,
                        )
                    )

                response.raise_for_status()
                return response
            except RuntimeError:
                raise
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    label = context or url
                    print(
                        f"Ошибка загрузки ({request_kind}) {label}. "
                        f"Попытка {attempt}/{self.max_retries}: {exc}"
                    )
                    sleep(attempt)
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError(f"Не удалось загрузить страницу: {url}")

    def _parse_listing(self, html: str, source_url: str | None = None) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        page_text = self._clean_text(soup.get_text(" ", strip=True))
        title = self._extract_title(soup)
        description = self._extract_description(soup)
        attribute_pairs, enabled_features, disabled_features = self._extract_attribute_data(soup)
        city, address_text = self._extract_city_and_address(soup)
        district = self._extract_district(title)
        floor, floors_total = self._extract_floor_info(attribute_pairs, title)
        price_local = self._extract_price(soup, attribute_pairs)
        currency = self._extract_currency(soup)

        listing = {
            "source_listing_id": self._extract_listing_id(
                self._extract_url(soup, source_url)
            ),
            "url": self._extract_url(soup, source_url),
            "city": city,
            "district": district,
            "address_text": address_text,
            "property_type": "apartment",
            "rooms": self._stringify(
                self._parse_numeric(attribute_pairs.get("Number of Rooms"))
                or self._extract_rooms(title)
            ),
            "area_m2": self._stringify(
                self._parse_float(attribute_pairs.get("Floor Area"))
                or self._extract_area(title)
            ),
            "floor": self._stringify(floor),
            "floors_total": self._stringify(floors_total),
            "price_local": self._stringify(price_local),
            "currency": currency,
            "deposit_local": self._stringify(self._extract_deposit(description, page_text)),
            "furnished": attribute_pairs.get("Furniture", "") or self._infer_furnished(description),
            "owner_type": self._extract_owner_type(soup, page_text),
            "elevator": self._extract_elevator(attribute_pairs, enabled_features, disabled_features),
            "parking": self._extract_parking(enabled_features, disabled_features, page_text),
            "balcony": self._extract_balcony(attribute_pairs),
            "renovation": attribute_pairs.get("Renovation", "") or self._infer_renovation(description),
            "pets_allowed": self._extract_permission_flag(
                attribute_pairs.get("Pets Allowed", ""),
                positive_patterns=[r"\bpets\s+allowed\b", r"\bwith pets\b"],
                negative_patterns=[r"\bno pets\b", r"\bpets not allowed\b"],
                text=page_text,
            ),
            "children_allowed": self._extract_permission_flag(
                attribute_pairs.get("Children Are Welcome", ""),
                positive_patterns=[r"\bchildren are welcome\b", r"\bwith children\b"],
                negative_patterns=[r"\bno children\b", r"\bchildren not allowed\b"],
                text=page_text,
            ),
            "description": description,
            "posted_at": self._extract_posted_at(soup),
        }
        return listing

    def _extract_listing_links_from_search_html(
        self,
        html: str,
        search_url: str,
        page_number: int,
    ) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict[str, str]] = []
        seen_ids: set[str] = set()

        for link in soup.select("a[href]"):
            href = link.get("href") or ""
            listing_id = self._extract_listing_id(href)
            if not listing_id or listing_id in seen_ids:
                continue

            text = self._clean_text(link.get_text(" ", strip=True))
            if not self._looks_like_search_result_link(text):
                continue

            price_el = link.select_one(".p") or link.select_one(".price")
            price_summary = self._clean_text(price_el.get_text(" ", strip=True)) if price_el else ""
            if not price_summary:
                price_summary = self._extract_price_summary_from_text(text)

            title = text
            if price_summary and title.endswith(price_summary):
                title = self._clean_text(title[: -len(price_summary)])
            elif price_summary:
                title = self._clean_text(title.replace(price_summary, " "))

            listing_url = self._normalize_listing_url(href, search_url)
            rows.append(
                {
                    "page_number": str(page_number),
                    "position": str(len(rows) + 1),
                    "source_listing_id": listing_id,
                    "listing_url": listing_url,
                    "title": title or text,
                    "price_summary": price_summary,
                }
            )
            seen_ids.add(listing_id)

        return rows

    def _extract_title(self, soup: BeautifulSoup) -> str:
        h1 = soup.select_one("h1[itemprop='name']") or soup.select_one("h1")
        return self._clean_text(h1.get_text(" ", strip=True)) if h1 else ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        description_el = soup.select_one(".body[itemprop='description']") or soup.select_one(".body")
        if description_el:
            return self._clean_text(description_el.get_text(" ", strip=True))

        meta_description = soup.find("meta", attrs={"name": "description"})
        if meta_description and meta_description.get("content"):
            return self._clean_text(meta_description["content"])
        return ""

    def _extract_attribute_data(
        self,
        soup: BeautifulSoup,
    ) -> tuple[dict[str, str], set[str], set[str]]:
        attribute_pairs: dict[str, str] = {}
        enabled_features: set[str] = set()
        disabled_features: set[str] = set()

        for item in soup.select(".attr .at2"):
            texts = [
                self._clean_text(node.get_text(" ", strip=True))
                for node in item.select("p")
                if self._clean_text(node.get_text(" ", strip=True))
            ]
            if not texts:
                continue

            if len(texts) >= 2:
                first, second = texts[0], texts[1]
                if second in self.known_attribute_labels:
                    attribute_pairs[second] = first
                elif first in self.known_attribute_labels:
                    attribute_pairs[first] = second
                else:
                    attribute_pairs[first] = second
                continue

            feature = texts[0]
            if "disabled" in (item.get("class") or []):
                disabled_features.add(feature)
            else:
                enabled_features.add(feature)

        return attribute_pairs, enabled_features, disabled_features

    def _extract_city_and_address(self, soup: BeautifulSoup) -> tuple[str, str]:
        location_el = soup.select_one(".loc")
        location_text = self._clean_text(location_el.get_text(" ", strip=True)) if location_el else ""
        if not location_text:
            return "", ""

        parts = [part.strip() for part in location_text.split(",") if part.strip()]
        if len(parts) == 1:
            return parts[0], ""
        return parts[-1], ", ".join(parts[:-1])

    def _extract_district(self, title: str) -> str:
        if not title:
            return ""

        before_metrics = re.split(r",\s*\d", title, maxsplit=1)[0]
        if " in " in before_metrics:
            return self._clean_text(before_metrics.rsplit(" in ", 1)[-1])
        return ""

    def _extract_floor_info(
        self,
        attribute_pairs: dict[str, str],
        title: str,
    ) -> tuple[int | None, int | None]:
        floor = self._parse_numeric(attribute_pairs.get("Floor"))
        floors_total = self._parse_numeric(attribute_pairs.get("Floors in the Building"))
        if floor is not None or floors_total is not None:
            return floor, floors_total

        match = re.search(r"(\d+)\s*/\s*(\d+)\s*floor", title, re.IGNORECASE)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None, None

    def _extract_price(self, soup: BeautifulSoup, attribute_pairs: dict[str, str]) -> int | None:
        price_el = soup.select_one(".price[itemprop='price']")
        if price_el and price_el.get("content"):
            return self._parse_numeric(price_el["content"])
        return self._parse_numeric(attribute_pairs.get("Price"))

    def _extract_currency(self, soup: BeautifulSoup) -> str:
        currency_meta = soup.select_one("meta[itemprop='priceCurrency']")
        if currency_meta and currency_meta.get("content"):
            return self._clean_text(currency_meta["content"])

        price_text = self._clean_text(
            soup.select_one(".price").get_text(" ", strip=True)
        ) if soup.select_one(".price") else ""
        if "֏" in price_text:
            return "AMD"
        if "$" in price_text:
            return "USD"
        if "€" in price_text:
            return "EUR"
        return ""

    def _extract_deposit(self, description: str, page_text: str) -> int | None:
        for source in (description, page_text):
            match = re.search(
                r"(?:security\s+deposit|deposit|депозит)(?:\s*[:\-]?\s*|\s+)(\d[\d\s.,]*)",
                source,
                re.IGNORECASE,
            )
            if match:
                return self._parse_numeric(match.group(1))
        return None

    def _infer_furnished(self, description: str) -> str:
        lowered = description.lower()
        if any(pattern in lowered for pattern in ("furnished", "мебель", "մեբել")):
            return "with"
        return ""

    def _extract_owner_type(self, soup: BeautifulSoup, page_text: str) -> str:
        user_block = self._clean_text(
            soup.select_one("#uinfo").get_text(" ", strip=True)
        ) if soup.select_one("#uinfo") else ""
        combined = user_block.lower()
        if "agency" in combined or "real estate" in combined:
            return "agency"
        if user_block:
            return "owner"
        return ""

    def _extract_elevator(
        self,
        attribute_pairs: dict[str, str],
        enabled_features: set[str],
        disabled_features: set[str],
    ) -> str:
        value = attribute_pairs.get("Elevator", "")
        if value:
            return self._normalize_booleanish(value)
        if "Elevator" in enabled_features:
            return "true"
        if "Elevator" in disabled_features:
            return "false"
        return ""

    def _extract_parking(
        self,
        enabled_features: set[str],
        disabled_features: set[str],
        page_text: str,
    ) -> str:
        parking_markers = {"Outdoor", "Covered", "Garage"}
        if enabled_features.intersection(parking_markers):
            return "true"
        if disabled_features.intersection(parking_markers):
            return "false"
        lowered = page_text.lower()
        if "parking" in lowered or "garage" in lowered:
            return "true"
        return ""

    def _extract_balcony(self, attribute_pairs: dict[str, str]) -> str:
        value = attribute_pairs.get("Balcony", "")
        if not value:
            return ""
        return self._normalize_booleanish(value)

    def _infer_renovation(self, description: str) -> str:
        lowered = description.lower()
        if "дизайнер" in lowered:
            return "Designer"
        if "капитальный" in lowered or "new repair" in lowered:
            return "Renovated"
        return ""

    def _extract_permission_flag(
        self,
        attribute_value: str,
        positive_patterns: list[str],
        negative_patterns: list[str],
        text: str,
    ) -> str:
        normalized = self._normalize_permission_value(attribute_value)
        if normalized:
            return normalized

        lowered = text.lower()
        for pattern in negative_patterns:
            if re.search(pattern, lowered):
                return "false"
        for pattern in positive_patterns:
            if re.search(pattern, lowered):
                return "true"
        return ""

    def _extract_posted_at(self, soup: BeautifulSoup) -> str:
        posted_el = soup.select_one("[itemprop='datePosted']")
        if posted_el and posted_el.get("content"):
            return self._clean_text(posted_el["content"])

        footer = self._clean_text(soup.select_one(".footer").get_text(" ", strip=True)) if soup.select_one(".footer") else ""
        match = re.search(r"Posted\s+(\d{2}\.\d{2}\.\d{4})", footer, re.IGNORECASE)
        if match:
            return match.group(1)

        renewed_match = re.search(
            r"Renewed\s+(\d{2}\.\d{2}\.\d{4}(?:,\s*\d{2}:\d{2})?)",
            footer,
            re.IGNORECASE,
        )
        if renewed_match:
            return renewed_match.group(1)
        return ""

    def _extract_url(self, soup: BeautifulSoup, source_url: str | None) -> str:
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            return self._normalize_listing_url(canonical["href"], self.default_search_base_url)
        return self._normalize_listing_url(source_url, self.default_search_base_url) if source_url else ""

    def _extract_listing_id(self, value: str | None) -> str:
        if not value:
            return ""
        match = re.search(r"/item/(\d+)", value)
        if match:
            return match.group(1)
        return ""

    def _extract_rooms(self, title: str) -> int | None:
        match = re.search(r"(\d+)\s+room", title, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _extract_area(self, title: str) -> float | int | None:
        return self._parse_float_from_text(title, r"(\d+(?:[.,]\d+)?)\s*sq\.m\.", re.IGNORECASE)

    def _looks_like_search_result_link(self, text: str) -> bool:
        if not text or text.lower() in {"english", "русский", "հայերեն"}:
            return False
        lowered = text.lower()
        markers = ("monthly", "room apartment", "sq.m.", "floor", "apartment")
        return any(marker in lowered for marker in markers) or bool(
            re.search(r"[\d,.]+\s*[֏$€₽]", text)
        )

    def _extract_price_summary_from_text(self, text: str) -> str:
        match = re.search(
            r"(\d[\d,.\s]*\s*[֏$€₽]\s*(?:monthly|daily)?)",
            text,
            re.IGNORECASE,
        )
        return self._clean_text(match.group(1)) if match else ""

    def _normalize_listing_url(self, href: str | None, base_url: str) -> str:
        if not href:
            return ""
        absolute_url = urljoin(base_url, href)
        parsed = urlparse(absolute_url)
        netloc = parsed.netloc or "www.list.am"
        if netloc.startswith("m."):
            netloc = "www.list.am"
        return urlunparse(parsed._replace(scheme="https", netloc=netloc))

    def _build_search_page_url(self, search_url: str, page_number: int) -> str:
        parsed = urlparse(search_url)
        path = parsed.path.rstrip("/")
        path = re.sub(r"/\d+$", "", path)
        if page_number > 1:
            path = f"{path}/{page_number}"
        if not path:
            path = "/"
        return urlunparse(parsed._replace(path=path))

    def _is_block_page(self, html: str) -> bool:
        lowered = html.lower()
        return (
            "just a moment..." in lowered
            or "challenges.cloudflare.com" in lowered
            or "cf-chl-" in lowered
            or "cf-browser-verification" in lowered
        )

    def _build_blocked_error_message(self, request_kind: str, url: str) -> str:
        fallback_flag = "--search-html-file" if request_kind == "search" else "--html-file"
        return (
            "List.am вернул anti-bot страницу вместо объявления. "
            f"Для этого источника используй сохранённый HTML через {fallback_flag}. "
            f"URL: {url}"
        )

    def _normalize_booleanish(self, value: str) -> str:
        lowered = self._clean_text(value).lower()
        if lowered in {"yes", "available", "with", "open", "true"}:
            return "true"
        if lowered in {"no", "not available", "without", "false"}:
            return "false"
        return "true"

    def _normalize_permission_value(self, value: str) -> str:
        lowered = self._clean_text(value).lower()
        if lowered in {"yes", "allowed", "welcome"}:
            return "true"
        if lowered in {"no", "not allowed"}:
            return "false"
        if lowered in {"negotiable", "by agreement"}:
            return "negotiable"
        return ""

    def _parse_numeric(self, value: str | None) -> int | None:
        if not value:
            return None
        digits = re.sub(r"[^\d]", "", value)
        if not digits:
            return None
        return int(digits)

    def _parse_float(self, value: str | None) -> float | int | None:
        if not value:
            return None
        match = re.search(r"(\d+(?:[.,]\d+)?)", value)
        if not match:
            return None
        number = float(match.group(1).replace(",", "."))
        return int(number) if number.is_integer() else number

    def _parse_float_from_text(
        self,
        text: str,
        pattern: str,
        flags: int = 0,
    ) -> float | int | None:
        match = re.search(pattern, text, flags)
        if not match:
            return None
        number = float(match.group(1).replace(",", "."))
        return int(number) if number.is_integer() else number

    def _clean_text(self, value: str | None) -> str:
        if not value:
            return ""
        value = value.replace("\xa0", " ")
        return re.sub(r"\s+", " ", value).strip()

    def _stringify(self, value: object) -> str:
        return "" if value is None else str(value)
