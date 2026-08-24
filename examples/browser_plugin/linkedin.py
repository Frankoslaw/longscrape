"""Receive browser captures and extract public LinkedIn page content.

Run with ``uv run uvicorn examples.browser_plugin.linkedin:app``.
This educational example is not production-ready. LinkedIn is a protected site;
automated collection may violate its Terms of Service. Use only with explicit
authorisation and at your own risk.
"""

import json
from collections.abc import AsyncIterator
from typing import cast
from urllib.parse import urljoin

from longscrape import (
    Context,
    Document,
    Extractor,
    Record,
)
from longscrape.browser_capture import BrowserCapture, BrowserCaptureServer
from longscrape.storage import CollisionPolicy
from parsel import Selector

from ..common import close_store, get_document_store, get_record_store

SEARCH_KIND = "linkedin.people-search"
PROFILE_KIND = "linkedin.profile"
people_store = get_record_store("linkedin_people")
profile_store = get_record_store("linkedin_profiles")
document_store = get_document_store()


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
        document: Document,
        context: Context,
    ) -> AsyncIterator[Record]:
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
        document: Document,
        context: Context,
    ) -> AsyncIterator[Record]:
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


async def handle_capture(capture: BrowserCapture) -> AsyncIterator[Record]:
    document = Document(
        url=capture.url,
        content=capture.content.encode("utf-8"),
        content_type=capture.content_type,
    )
    await document_store.put(document, key=f"{capture.kind}:{document.url}")
    match capture.kind:
        case "linkedin.people-search":
            records = PeopleSearchExtractor().extract(document, Context())
        case "linkedin.profile":
            records = ProfileExtractor().extract(document, Context())
        case _:
            return

    async for record in records:
        if record.kind == "person":
            await people_store.put(
                record,
                key=cast(str, record.data["profile_url"]),
                policy=CollisionPolicy.MERGE,
            )
        else:
            await profile_store.put(
                record, key=document.url, policy=CollisionPolicy.MERGE
            )
        print(json.dumps(record.data, ensure_ascii=False))
        yield record


capture_server = BrowserCaptureServer(handle_capture)
app = capture_server.app


@app.on_event("shutdown")
async def close_stores() -> None:
    await close_store(document_store)
    await close_store(people_store)
    await close_store(profile_store)
