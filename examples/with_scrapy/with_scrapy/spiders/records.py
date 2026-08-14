"""Minimal spiders that delegate core conversion to longscrape-scrapy."""

from longscrape_scrapy import IdentityCrawler, UrlCrawler


class UrlDocumentSpider(UrlCrawler):
    """Fetch an InputUrl and send its native document item through pipelines."""

    name = "url"


class IdentityInputSpider(IdentityCrawler):
    """Send an InputDocument or InputQuery as native items through pipelines."""

    name = "identity"
