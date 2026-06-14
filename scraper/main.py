from __future__ import annotations

import argparse
import re
from pathlib import Path
from time import sleep

from bs4 import BeautifulSoup

from scraper.scrapers.base_scraper import BaseScraper
from scraper.scrapers.scraper_factory import ScraperFactory


def build_default_output_path(site_name: str) -> Path:
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "data" / "relocation" / f"{site_name}_listings.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Скрейпер объявлений аренды с сохранением в CSV."
    )
    parser.add_argument(
        "--url",
        help="Ссылка на карточку объявления.",
    )
    parser.add_argument(
        "--search-url",
        help="Ссылка на страницу поисковой выдачи. Если указана, скрейпер обойдёт несколько страниц, соберёт ссылки и затем загрузит карточки объявлений.",
    )
    parser.add_argument(
        "--html-file",
        help="Путь к локальному HTML-файлу. Скрейпер сам определит, что это: карточка объявления или поисковая выдача.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="Сколько страниц выдачи обойти при использовании --search-url.",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="С какой страницы выдачи начинать обход при использовании --search-url или какое значение поставить в page_number для --search-html-file.",
    )
    parser.add_argument(
        "--links-output",
        help="Необязательный путь к CSV со списком найденных ссылок из выдачи.",
    )
    parser.add_argument(
        "--delay-sec",
        type=float,
        default=0.0,
        help="Пауза между HTTP-запросами в секундах. Удобно для больших прогонов по выдаче.",
    )
    parser.add_argument(
        "--output",
        help="Путь к CSV-файлу. Если файл уже существует, запись будет добавлена или обновлена по source_listing_id.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.pages < 1:
        print("Параметр --pages должен быть не меньше 1.")
        return
    if args.start_page < 1:
        print("Параметр --start-page должен быть не меньше 1.")
        return

    input_modes = [
        bool(args.url),
        bool(args.html_file),
        bool(args.search_url),
    ]
    if sum(input_modes) == 0:
        print("Нужно передать один из параметров: --url, --html-file или --search-url.")
        return
    if sum(input_modes) > 1:
        print("Используй только один режим за запуск: --url, --html-file или --search-url.")
        return

    html = None
    if args.html_file:
        html = read_html_file(args.html_file)
        if html is None:
            return

    site_name = detect_site_name(
        direct_url=args.url,
        search_url=args.search_url,
        html=html,
    )
    if not site_name:
        print("Не удалось определить сайт по URL или HTML.")
        return

    scraper = ScraperFactory.get_scraper(
        url=args.url or args.search_url,
        site_name=site_name,
    )
    if scraper is None:
        print("Не удалось определить подходящий скрейпер.")
        return

    output_path = args.output or str(build_default_output_path(scraper.site_name))

    is_search_html_mode = bool(args.html_file and html and looks_like_search_html(html, site_name))

    if args.search_url or is_search_html_mode:
        search_url = args.search_url or infer_search_url_from_html(html or "", scraper)
        if not search_url:
            search_url = scraper.default_search_base_url
        if not search_url:
            print("Не удалось определить базовый URL поисковой выдачи для HTML.")
            return

        try:
            if args.search_url:
                search_rows = scraper.collect_listing_links(
                    search_url,
                    pages=args.pages,
                    start_page=args.start_page,
                    delay_sec=args.delay_sec,
                )
            else:
                search_rows = collect_listing_links_from_html(
                    scraper=scraper,
                    html=html or "",
                    search_url=search_url,
                    page_number=infer_page_number_from_html(html or "", default=args.start_page),
                )
        except Exception as exc:
            print(f"Не удалось извлечь ссылки из поисковой выдачи: {exc}")
            return

        if not search_rows:
            print("Не удалось извлечь ссылки из поисковой выдачи.")
            return

        if args.links_output:
            save_search_results(scraper, search_rows, args.links_output)
            print(f"CSV со ссылками обновлён: {Path(args.links_output).resolve()}")

        if args.search_url:
            print(
                f"Найдено объявлений в выдаче: {len(search_rows)} "
                f"(страницы: {args.start_page}-{args.start_page + args.pages - 1})"
            )
        else:
            print(
                f"Найдено объявлений в локальном search HTML: {len(search_rows)} "
                f"(page_number={infer_page_number_from_html(html or '', default=args.start_page)})"
            )

        pending_rows: list[dict[str, str]] = []
        processed_count = 0
        total_links = len(search_rows)
        batch_size = 20

        for index, row in enumerate(search_rows, start=1):
            listing_url = row["listing_url"]
            print(
                f"[{index}/{total_links}] Загружаю объявление "
                f"{row.get('source_listing_id', '')}: {listing_url}"
            )
            try:
                pending_rows.extend(scraper.scrape(url=listing_url))
                processed_count += 1
            except Exception as exc:
                print(f"Не удалось обработать {listing_url}: {exc}")

            if pending_rows and (index % batch_size == 0 or index == total_links):
                scraper.save_to_csv(pending_rows, output_path)
                print(
                    f"Промежуточно сохранено записей: {len(pending_rows)} "
                    f"в {Path(output_path).resolve()}"
                )
                pending_rows = []

            if args.delay_sec > 0 and index < total_links:
                sleep(args.delay_sec)

        print(f"Успешно обработано объявлений: {processed_count}")
        if getattr(scraper, "last_search_page_errors", None):
            print("Пропущенные страницы выдачи:")
            for error_row in scraper.last_search_page_errors:
                print(
                    f"- page {error_row['page_number']}: "
                    f"{error_row['page_url']}"
                )
        print(f"CSV обновлён: {Path(output_path).resolve()}")
        return

    try:
        listings = scraper.scrape(url=args.url, html=html)
    except Exception as exc:
        print(f"Не удалось извлечь данные из объявления: {exc}")
        return

    if not listings:
        print("Не удалось извлечь данные из объявления.")
        return

    scraper.save_to_csv(listings, output_path)
    print(f"Сохранено записей: {len(listings)}")
    print(f"CSV обновлён: {Path(output_path).resolve()}")


def read_html_file(file_path: str) -> str | None:
    html_path = Path(file_path).expanduser().resolve()
    if not html_path.exists():
        print(f"HTML-файл не найден: {html_path}")
        return None
    return html_path.read_text(encoding="utf-8", errors="ignore")


def detect_site_name(
    direct_url: str | None = None,
    search_url: str | None = None,
    html: str | None = None,
) -> str | None:
    scraper = ScraperFactory.get_scraper(direct_url or search_url)
    if scraper is not None:
        return scraper.site_name

    lowered = (html or "").lower()
    if (
        "list.am" in lowered
        or "on list.am since" in lowered
        or re.search(r"/(?:en|ru|am)/item/\d+", lowered)
        or re.search(r"/category/56(?:/|\"|'|\\s|<)", lowered)
    ):
        return "listam"
    if "krisha.kz" in lowered or "window.data" in lowered or "offer__advert-title" in lowered:
        return "krisha"
    return None


def looks_like_search_html(html: str, site_name: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")

    if site_name == "krisha":
        return bool(soup.select(".a-card[data-id]")) and not bool(
            soup.select_one(".offer__advert-title") or soup.select_one("#jsdata")
        )

    if site_name == "listam":
        item_links = [
            a
            for a in soup.select("a[href]")
            if re.search(r"/(?:[a-z]{2}/)?item/\d+", a.get("href", ""))
        ]
        has_listing_markers = bool(
            soup.select_one("[itemprop='datePosted']")
            or soup.select_one(".body[itemprop='description']")
            or soup.select_one(".price[itemprop='price']")
        )
        return len(item_links) >= 2 and not has_listing_markers

    return False


def infer_search_url_from_html(html: str, scraper: BaseScraper) -> str:
    patterns = [
        r"https://(?:www\.)?list\.am/(?:[a-z]{2}/)?category/\d+(?:/\d+)?",
        r"https://(?:m\.)?krisha\.kz/arenda/kvartiry/[^\s\"']*",
        r"https://krisha\.kz/arenda/kvartiry/[^\s\"']*",
        r"/(?:[a-z]{2}/)?category/\d+(?:/\d+)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if not match:
            continue
        value = match.group(0)
        if value.startswith("/"):
            if "list.am" in html.lower():
                return f"https://www.list.am{value}"
        return value
    return scraper.default_search_base_url


def infer_page_number_from_html(html: str, default: int = 1) -> int:
    match = re.search(r"/category/\d+/(\d+)", html)
    if match:
        return int(match.group(1))
    match = re.search(r"[?&]page=(\d+)", html)
    if match:
        return int(match.group(1))
    return default


def collect_listing_links_from_html(
    scraper: BaseScraper,
    html: str,
    search_url: str,
    page_number: int,
) -> list[dict[str, str]]:
    if not hasattr(scraper, "collect_listing_links_from_html"):
        raise RuntimeError("У выбранного скрейпера нет поддержки search HTML.")
    return scraper.collect_listing_links_from_html(
        html=html,
        search_url=search_url,
        page_number=page_number,
    )


def save_search_results(
    scraper: BaseScraper,
    rows: list[dict[str, str]],
    output_filename: str,
) -> None:
    if not hasattr(scraper, "save_search_results_to_csv"):
        raise RuntimeError("У выбранного скрейпера нет поддержки сохранения search-результатов.")
    scraper.save_search_results_to_csv(rows, output_filename)


if __name__ == "__main__":
    main()
