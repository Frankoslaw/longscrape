"""Extract browser-captured LinkedIn pages through a kind-routed scraper.

Run with ``uv run uvicorn --app-dir examples/browser-plugin linkedin:app``.
Only use this example with pages and data you are authorised to process.
"""

import json
from urllib.parse import urljoin

from longscrape import CaptureScraper
from longscrape.capture import create_capture_app
from longscrape_core import (
    Document,
    Extractor,
    InMemoryDocumentStore,
    InMemoryJobQueue,
    InMemoryRecordStore,
    Job,
    Record,
)
from parsel import Selector

SEARCH_KIND = "linkedin.people-search"
PROFILE_KIND = "linkedin.profile"


def compact_text(values: list[str]) -> str:
    return " ".join(value.strip() for value in values if value.strip())


def title_name(selector: Selector) -> str:
    title = selector.css("meta[property='og:title']::attr(content), title::text").get(
        ""
    )
    return title.removesuffix(" | LinkedIn").strip()


class LinkedInPeopleSearchExtractor(Extractor):
    async def extract(self, job: Job, document: Document, queue) -> list[Record]:
        selector = Selector(text=document.text)
        records: list[Record] = []
        seen_urls: set[str] = set()
        for link in selector.xpath("//a[contains(@href, '/in/')]"):
            href = link.attrib.get("href")
            if not href:
                continue
            url = urljoin(document.url, href).split("?", maxsplit=1)[0]
            if "/in/" not in url or url in seen_urls:
                continue
            seen_urls.add(url)
            name = compact_text(link.css("span[aria-hidden='true']::text").getall())
            if not name:
                name = compact_text(link.css("::text").getall())
            if not name:
                name = link.attrib.get("aria-label", "").strip()
            if name:
                records.append(
                    Record(
                        kind=job.kind,
                        source_url=url,
                        document=document,
                        data={"name": name, "profile_url": url},
                    )
                )
        return records


class LinkedInProfileExtractor(Extractor):
    async def extract(self, job: Job, document: Document, queue) -> list[Record]:
        selector = Selector(text=document.text)
        top_card = selector.xpath("//*[contains(@id, 'Topcard')]")
        name = str(job.context.get("profile_name", "")).strip()
        if not name:
            name = compact_text(top_card.xpath(".//h2[1]//text()").getall())
        if not name:
            name = compact_text(selector.css("main h1::text, h1::text").getall())
        if not name:
            name = title_name(selector)
        headline = str(job.context.get("profile_headline", "")).strip()
        if not headline:
            headline = compact_text(
                selector.css("main .text-body-medium::text").getall()
            )
        return [
            Record(
                kind=job.kind,
                source_url=document.url,
                document=document,
                data={"name": name, "headline": headline},
            )
        ]


async def print_record(record: Record) -> None:
    print(json.dumps(record.data, ensure_ascii=False))


scraper = CaptureScraper(
    {
        SEARCH_KIND: LinkedInPeopleSearchExtractor(),
        PROFILE_KIND: LinkedInProfileExtractor(),
    },
    queue=InMemoryJobQueue(),
    document_store=InMemoryDocumentStore(),
    record_store=InMemoryRecordStore(),
    on_record=print_record,
)
app = create_capture_app(scraper.scrape)
