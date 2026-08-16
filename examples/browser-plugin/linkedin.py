"""Receive browser captures and extract public LinkedIn page content.

Run with ``uv run uvicorn --app-dir examples/browser-plugin linkedin:app``.
Only process pages and data you are authorised to access.
"""

import json
from collections.abc import AsyncIterable, AsyncIterator
from urllib.parse import urljoin

from longscrape import (
    DISCARD_SUBMITTER,
    BrowserCaptureServer,
    Document,
    Extractor,
    Job,
    JobSubmitter,
    Record,
)
from parsel import Selector

SEARCH_KIND = "linkedin.people-search"
PROFILE_KIND = "linkedin.profile"


def text(values: list[str]) -> str:
    return " ".join(value.strip() for value in values if value.strip())


class PeopleSearchExtractor(Extractor):
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        submitter: JobSubmitter = DISCARD_SUBMITTER,
    ) -> AsyncIterator[Record]:
        async for document in documents:
            page = Selector(text=document.content.decode(errors="replace"))
            seen: set[str] = set()
            for link in page.xpath("//a[contains(@href, '/in/')]"):
                href = link.attrib.get("href")
                if not href:
                    continue
                url = urljoin(document.url, href).split("?", maxsplit=1)[0]
                if url in seen:
                    continue
                seen.add(url)
                name = text(link.css("span[aria-hidden='true']::text").getall())
                if name:
                    yield Record(kind="person", data={"name": name, "profile_url": url})


class ProfileExtractor(Extractor):
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        submitter: JobSubmitter = DISCARD_SUBMITTER,
    ) -> AsyncIterator[Record]:
        async for document in documents:
            page = Selector(text=document.content.decode(errors="replace"))
            name = text(page.css("main h1::text, h1::text").getall())
            if not name:
                name = page.css("meta[property='og:title']::attr(content)").get("")
                name = name.removesuffix(" | LinkedIn").strip()
            headline = text(page.css("main .text-body-medium::text").getall())
            yield Record(kind="profile", data={"name": name, "headline": headline})


async def print_records(records: list[Record]) -> None:
    for record in records:
        print(json.dumps(record.data, ensure_ascii=False))


capture_server = BrowserCaptureServer(
    {SEARCH_KIND: PeopleSearchExtractor(), PROFILE_KIND: ProfileExtractor()},
    on_records=print_records,
)
app = capture_server.app
