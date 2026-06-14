from __future__ import annotations

import json
import re
from html import unescape
from time import sleep
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

from scraper.scrapers.base_scraper import BaseScraper


class KrishaScraper(BaseScraper):
    site_name = "krisha"
    default_search_base_url = "https://krisha.kz/arenda/kvartiry/"
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
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    search_connect_timeout_sec = 8
    search_read_timeout_sec = 25
    search_max_retries = 3
    listing_connect_timeout_sec = 8
    listing_read_timeout_sec = 15
    listing_max_retries = 2

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

        listing = self._parse_listing(html, source_url=url)
        return [listing]

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
        canonical_base_url = search_url
        self.last_search_page_errors = []

        end_page = start_page + pages - 1

        for page_number in range(start_page, end_page + 1):
            page_url = self._build_search_page_url(canonical_base_url, page_number)
            print(
                f"Загружаю страницу выдачи {page_number}/{end_page}: {page_url}"
            )

            response = None
            last_exception: requests.RequestException | None = None
            for candidate_url in self._build_search_fallback_urls(page_url):
                if candidate_url != page_url:
                    print(
                        f"Пробую fallback для страницы {page_number}: "
                        f"{candidate_url}"
                    )
                try:
                    response = self._fetch_response(
                        candidate_url,
                        request_kind="search",
                        context=f"страница выдачи {page_number}",
                    )
                    break
                except requests.RequestException as exc:
                    last_exception = exc

            if response is None:
                self.last_search_page_errors.append(
                    {
                        "page_number": str(page_number),
                        "page_url": page_url,
                        "error": str(last_exception) if last_exception else "",
                    }
                )
                print(
                    f"Не удалось загрузить страницу выдачи {page_number}: "
                    f"{page_url} -> {last_exception}"
                )
                if delay_sec > 0 and page_number < end_page:
                    sleep(delay_sec)
                continue

            if page_number == 1:
                canonical_base_url = response.url

            page_rows = self._extract_listing_links_from_search_html(
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

    def save_search_results_to_csv(self, rows: list[dict[str, str]], output_filename: str) -> None:
        self.save_rows_to_csv(
            rows=rows,
            output_filename=output_filename,
            fieldnames=self.search_result_fieldnames,
            dedupe_key="source_listing_id",
        )

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
        connect_timeout_sec, read_timeout_sec, max_retries = self._get_request_settings(
            request_kind
        )
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self._session.get(
                    url,
                    timeout=(connect_timeout_sec, read_timeout_sec),
                )
                response.raise_for_status()
                response.encoding = response.encoding or "utf-8"
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt < max_retries:
                    label = context or url
                    print(
                        f"Ошибка загрузки ({request_kind}) {label}. "
                        f"Попытка {attempt}/{max_retries}: {exc}"
                    )
                    sleep(attempt)
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError(f"Не удалось загрузить страницу: {url}")

    def _get_request_settings(self, request_kind: str) -> tuple[int, int, int]:
        if request_kind == "search":
            return (
                self.search_connect_timeout_sec,
                self.search_read_timeout_sec,
                self.search_max_retries,
            )
        return (
            self.listing_connect_timeout_sec,
            self.listing_read_timeout_sec,
            self.listing_max_retries,
        )

    def _parse_listing(self, html: str, source_url: str | None = None) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        window_data = self._extract_window_data(soup)
        advert = window_data.get("advert", {})
        adverts = window_data.get("adverts") or []
        advert_card = adverts[0] if adverts else {}

        short_info = self._extract_short_info(soup)
        parameters = self._extract_parameters(soup)
        page_text = self._clean_text(soup.get_text(" ", strip=True))
        description = self._extract_description(soup, advert_card)
        title = self._extract_title(soup, advert, advert_card)

        location_text = short_info.get("Город", "")
        city, district = self._extract_city_and_district(location_text, advert_card)
        floor, floors_total = self._extract_floor_info(short_info.get("Этаж", ""), title)
        price_local = self._extract_price(advert, advert_card, soup)
        currency = self._extract_currency(soup, advert_card)
        deposit_local = self._extract_deposit(description, page_text, price_local)
        furnished = self._extract_furnished(short_info, advert_card)
        owner_type = self._extract_owner_type(advert_card)
        renovation = short_info.get("Состояние квартиры", "")

        listing = {
            "source_listing_id": self._stringify(advert.get("id") or advert_card.get("id")),
            "url": self._extract_url(soup, source_url, advert_card),
            "city": city,
            "district": district,
            "address_text": self._extract_address_text(advert, advert_card, title),
            "property_type": self._extract_property_type(title, advert_card),
            "rooms": self._stringify(advert.get("rooms") or self._extract_rooms(title)),
            "area_m2": self._stringify(advert.get("square") or self._extract_area(short_info.get("Площадь", ""), title)),
            "floor": self._stringify(floor),
            "floors_total": self._stringify(floors_total),
            "price_local": self._stringify(price_local),
            "currency": currency,
            "deposit_local": self._stringify(deposit_local),
            "furnished": furnished,
            "owner_type": owner_type,
            "elevator": self._extract_elevator(parameters, page_text),
            "parking": self._extract_parking(parameters, page_text),
            "balcony": self._extract_balcony(parameters),
            "renovation": renovation,
            "pets_allowed": self._extract_explicit_flag(
                page_text,
                positive_patterns=[r"\bможно с животн", r"\bс животн(ыми)?\b"],
                negative_patterns=[r"\bбез животн", r"\bнельзя с животн"],
            ),
            "children_allowed": self._extract_explicit_flag(
                page_text,
                positive_patterns=[r"\bможно с деть", r"\bс детьми\b"],
                negative_patterns=[r"\bбез детей", r"\bнельзя с деть"],
            ),
            "description": description,
            "posted_at": advert_card.get("addedAt") or advert_card.get("createdAt") or "",
        }
        return listing

    def _extract_window_data(self, soup: BeautifulSoup) -> dict:
        script = soup.find("script", id="jsdata")
        if not script:
            return {}

        script_text = script.get_text()
        match = re.search(r"window\.data\s*=\s*(\{.*\});", script_text, re.DOTALL)
        if not match:
            return {}

        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return {}

    def _extract_listing_links_from_search_html(
        self,
        html: str,
        search_url: str,
        page_number: int,
    ) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        for card in soup.select(".a-card[data-id]"):
            listing_id = self._clean_text(card.get("data-id") or card.get("data-product-id") or "")
            title_el = card.select_one("a.a-card__title") or card.select_one("a.a-card__image") or card.select_one("a.a-card__photo")
            if not title_el or not title_el.get("href"):
                continue

            listing_url = self._normalize_listing_url(title_el["href"], search_url)
            if listing_url in seen_urls:
                continue
            seen_urls.add(listing_url)

            title = self._clean_text(title_el.get_text(" ", strip=True))
            price_el = card.select_one(".a-card__price")
            price_summary = self._clean_text(price_el.get_text(" ", strip=True)) if price_el else ""

            rows.append(
                {
                    "page_number": str(page_number),
                    "position": str(len(rows) + 1),
                    "source_listing_id": listing_id,
                    "listing_url": listing_url,
                    "title": title,
                    "price_summary": price_summary,
                }
            )

        return rows

    def _extract_short_info(self, soup: BeautifulSoup) -> dict[str, str]:
        result: dict[str, str] = {}
        for item in soup.select(".offer__short-description .offer__info-item"):
            title_el = item.select_one(".offer__info-title")
            value_el = item.select_one(".offer__advert-short-info")
            if not title_el or not value_el:
                continue
            title = self._clean_text(title_el.get_text(" ", strip=True))
            value = self._clean_text(value_el.get_text(" ", strip=True))
            result[title] = value
        return result

    def _extract_parameters(self, soup: BeautifulSoup) -> dict[str, str]:
        result: dict[str, str] = {}
        for block in soup.select(".offer__parameters dl"):
            key_el = block.find("dt")
            value_el = block.find("dd")
            if not key_el or not value_el:
                continue
            key = self._clean_text(key_el.get_text(" ", strip=True))
            value = self._clean_text(value_el.get_text(" ", strip=True))
            result[key] = value
        return result

    def _extract_title(self, soup: BeautifulSoup, advert: dict, advert_card: dict) -> str:
        h1 = soup.select_one(".offer__advert-title h1")
        if h1:
            return self._clean_text(h1.get_text(" ", strip=True))
        return self._clean_text(advert.get("title") or advert_card.get("title") or "")

    def _extract_description(self, soup: BeautifulSoup, advert_card: dict) -> str:
        description_el = soup.select_one(".offer__description .js-description")
        if description_el:
            return self._clean_text(description_el.get_text(" ", strip=True))
        return self._clean_text(advert_card.get("description") or "")

    def _extract_city_and_district(self, location_text: str, advert_card: dict) -> tuple[str, str]:
        cleaned = self._clean_location_text(location_text)
        if cleaned:
            parts = [part.strip() for part in cleaned.split(",") if part.strip()]
            city = parts[0] if parts else ""
            district = ", ".join(parts[1:]) if len(parts) > 1 else ""
            return city, district

        full_address = self._clean_location_text(advert_card.get("fullAddress") or "")
        if full_address:
            parts = [part.strip() for part in full_address.split(",") if part.strip()]
            city = parts[0] if parts else ""
            district = parts[1] if len(parts) > 1 else ""
            return city, district

        return "", ""

    def _extract_floor_info(self, floor_text: str, title: str) -> tuple[int | None, int | None]:
        for source in (floor_text, title):
            cleaned = self._clean_text(source)
            if not cleaned:
                continue
            match = re.search(r"(\d+)\s*(?:из|/)\s*(\d+)", cleaned)
            if match:
                return int(match.group(1)), int(match.group(2))
        return None, None

    def _extract_price(self, advert: dict, advert_card: dict, soup: BeautifulSoup) -> int | None:
        if advert.get("price"):
            return int(advert["price"])

        raw_price = advert_card.get("price")
        if raw_price:
            parsed = self._parse_numeric(raw_price)
            if parsed is not None:
                return parsed

        price_el = soup.select_one(".offer__price")
        if price_el:
            parsed = self._parse_numeric(price_el.get_text(" ", strip=True))
            if parsed is not None:
                return parsed
        return None

    def _extract_currency(self, soup: BeautifulSoup, advert_card: dict) -> str:
        raw_price = self._clean_text(str(advert_card.get("price") or ""))
        page_price = self._clean_text(
            soup.select_one(".offer__price").get_text(" ", strip=True)
        ) if soup.select_one(".offer__price") else ""
        combined = f"{raw_price} {page_price}"
        if "₸" in combined:
            return "KZT"
        if "$" in combined:
            return "USD"
        if "₽" in combined:
            return "RUB"
        return ""

    def _extract_deposit(self, description: str, page_text: str, price_local: int | None) -> int | None:
        for source in (description, page_text):
            match = re.search(
                r"(?:страховой\s+)?депозит(?:\s*[:\-]?\s*|\s+)(\d[\d\s.,]*)",
                source,
                re.IGNORECASE,
            )
            if not match:
                continue

            raw_number = match.group(1)
            parsed = self._parse_numeric(raw_number)
            if parsed is None:
                continue

            if parsed < 1000 and price_local and price_local >= 100000:
                return parsed * 1000
            return parsed
        return None

    def _extract_furnished(self, short_info: dict[str, str], advert_card: dict) -> str:
        if short_info.get("Квартира меблирована"):
            return short_info["Квартира меблирована"]

        description = self._clean_text(advert_card.get("description") or "").lower()
        if "меблирована полностью" in description:
            return "полностью"
        if "частично меблирована" in description:
            return "частично"
        return ""

    def _extract_owner_type(self, advert_card: dict) -> str:
        owner = advert_card.get("owner") or {}
        if owner.get("isOwner"):
            return "owner"
        if owner:
            return "agency"
        return ""

    def _extract_url(self, soup: BeautifulSoup, source_url: str | None, advert_card: dict) -> str:
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            return canonical["href"]

        card_url = advert_card.get("url")
        if card_url:
            return urljoin("https://krisha.kz", card_url)

        return source_url or ""

    def _extract_address_text(self, advert: dict, advert_card: dict, title: str) -> str:
        if advert_card.get("address"):
            return self._clean_text(advert_card["address"])
        if advert.get("addressTitle"):
            return self._clean_text(advert["addressTitle"])

        if "," in title:
            return self._clean_text(title.split(",")[-1])
        return ""

    def _extract_property_type(self, title: str, advert_card: dict) -> str:
        lower_title = title.lower()
        if "квартира" in lower_title:
            return "квартира"
        category = self._clean_text(
            (((advert_card.get("category") or {}).get("label")) or "")
        ).lower()
        if "квартир" in category:
            return "квартира"
        return ""

    def _extract_rooms(self, title: str) -> int | None:
        match = re.search(r"(\d+)-комнатн", title)
        if match:
            return int(match.group(1))
        return None

    def _extract_area(self, area_text: str, title: str) -> float | int | None:
        for source in (area_text, title):
            match = re.search(r"(\d+(?:[.,]\d+)?)\s*м²", source)
            if match:
                value = match.group(1).replace(",", ".")
                number = float(value)
                return int(number) if number.is_integer() else number
        return None

    def _extract_elevator(self, parameters: dict[str, str], page_text: str) -> str:
        facilities = parameters.get("Удобства", "").lower()
        if "лифт" in facilities:
            return "true"
        lowered = page_text.lower()
        if "лифта нет" in lowered:
            return "false"
        return ""

    def _extract_parking(self, parameters: dict[str, str], page_text: str) -> str:
        combined = " ".join(parameters.values()).lower() + " " + page_text.lower()
        if any(word in combined for word in ("паркинг", "парковка", "подземный паркинг", "гараж")):
            return "true"
        if "без парковки" in combined:
            return "false"
        return ""

    def _extract_balcony(self, parameters: dict[str, str]) -> str:
        balcony_value = parameters.get("Балкон", "").strip().lower()
        if not balcony_value:
            return ""
        if balcony_value in {"нет", "отсутствует"}:
            return "false"
        return "true"

    def _extract_explicit_flag(
        self,
        text: str,
        positive_patterns: list[str],
        negative_patterns: list[str],
    ) -> str:
        lowered = text.lower()
        for pattern in negative_patterns:
            if re.search(pattern, lowered):
                return "false"
        for pattern in positive_patterns:
            if re.search(pattern, lowered):
                return "true"
        return ""

    def _parse_numeric(self, value: str) -> int | None:
        digits = re.sub(r"[^\d]", "", unescape(value))
        if not digits:
            return None
        return int(digits)

    def _clean_text(self, value: str) -> str:
        if not value:
            return ""
        value = unescape(value)
        value = value.replace("\xa0", " ")
        return re.sub(r"\s+", " ", value).strip()

    def _clean_location_text(self, value: str) -> str:
        cleaned = self._clean_text(value)
        if not cleaned:
            return ""
        cleaned = re.sub(r"\bпоказать\s+на\s+карте\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+,", ",", cleaned)
        return self._clean_text(cleaned)

    def _build_search_page_url(self, search_url: str, page_number: int) -> str:
        if page_number <= 1:
            return search_url

        parsed = urlparse(search_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["page"] = str(page_number)
        updated_query = urlencode(query, doseq=True)
        return urlunparse(parsed._replace(query=updated_query))

    def _normalize_listing_url(self, href: str, base_url: str) -> str:
        absolute_url = urljoin(base_url, href)
        parsed = urlparse(absolute_url)
        return urlunparse(parsed._replace(scheme="https", netloc="krisha.kz"))

    def _build_search_fallback_urls(self, page_url: str) -> list[str]:
        urls = [page_url]
        parsed = urlparse(page_url)
        if parsed.netloc == "krisha.kz":
            mobile_url = urlunparse(parsed._replace(netloc="m.krisha.kz"))
            if mobile_url not in urls:
                urls.append(mobile_url)
        return urls

    def _stringify(self, value: object) -> str:
        return "" if value is None else str(value)
