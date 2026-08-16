"""Receive browser captures and extract public LinkedIn page content.

Run with ``uv run uvicorn --app-dir examples/browser-plugin linkedin:app``.
This educational example is not production-ready. LinkedIn is a protected site;
automated collection may violate its Terms of Service. Use only with explicit
authorisation and at your own risk.
"""

import json
import sys
from collections.abc import AsyncIterable, AsyncIterator
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import close_store, get_record_store
from longscrape import (
    DISCARD_SUBMITTER,
    Document,
    Extractor,
    InputDocument,
    Job,
    JobSubmitter,
    Record,
)
from longscrape.capture import BrowserCapture, BrowserCaptureServer
from parsel import Selector

SEARCH_KIND = "linkedin.people-search"
PROFILE_KIND = "linkedin.profile"
people_store = get_record_store("linkedin_people")
profile_store = get_record_store("linkedin_profiles")


def text(values: list[str]) -> str:
    return " ".join(value.strip() for value in values if value.strip())


def first_text(values: list[str]) -> str:
    for value in values:
        value = value.strip()
        if value and not value.startswith("•"):
            return value
    return ""


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
                name = first_text(link.xpath(".//text()").getall())
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
                name = page.css(
                    "meta[property='og:title']::attr(content), title::text"
                ).get("")
                name = name.removesuffix(" | LinkedIn").strip()
            headline = text(page.css("main .text-body-medium::text").getall())
            if not headline and name:
                headline = text(
                    page.xpath(
                        "//p[normalize-space() = $name][1]"
                        "/following-sibling::div[1]//text()",
                        name=name,
                    ).getall()
                )
            yield Record(kind="profile", data={"name": name, "headline": headline})


async def one(document: Document) -> AsyncIterator[Document]:
    yield document


async def handle_capture(capture: BrowserCapture) -> AsyncIterator[Record]:
    document = Document(
        url=capture.url,
        content=capture.content.encode("utf-8"),
        content_type=capture.content_type,
    )
    job = Job(kind=capture.kind, input=InputDocument(document), context=capture.context)
    match capture.kind:
        case "linkedin.people-search":
            records = PeopleSearchExtractor().extract(one(document), job)
        case "linkedin.profile":
            records = ProfileExtractor().extract(one(document), job)
        case _:
            return

    async for record in records:
        if record.kind == "person":
            await people_store.store(record)
        else:
            await profile_store.store(record)
        print(json.dumps(record.data, ensure_ascii=False))
        yield record


capture_server = BrowserCaptureServer(handle_capture)
app = capture_server.app


@app.on_event("shutdown")
async def close_stores() -> None:
    await close_store(people_store)
    await close_store(profile_store)
