from scraper.scrapers.base_scraper import BaseScraper
from scraper.scrapers.krisha.krisha_scraper import KrishaScraper
from scraper.scrapers.list_am.list_am_scraper import ListAmScraper
from urllib.parse import urlparse


class ScraperFactory:
    @staticmethod
    def get_scraper(url: str | None = None, site_name: str | None = None) -> BaseScraper | None:
        if site_name == "krisha":
            return KrishaScraper()
        if site_name == "listam":
            return ListAmScraper()

        if not url:
            return None

        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        if "krisha.kz" in domain:
            return KrishaScraper()
        if "list.am" in domain:
            return ListAmScraper()

        return None
