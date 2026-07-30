"""Receive browser-captured LinkedIn pages and extract public page content.

Run with ``uv run uvicorn --app-dir examples/browser-plugin linkedin:app``,
then load the ``extension`` directory as a temporary Firefox extension. Only
use this example with pages and data you are authorised to process.
"""

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urljoin

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from parsel import Selector
from pydantic import BaseModel, Field

from longscrape import (
    Crawler,
    DefaultExtractor,
    ExtractionResult,
    PipelineInput,
    RawEntry,
    RawInput,
    RichEntry,
    ScraperWorker,
)

SEARCH_KIND = "linkedin.people-search"
PROFILE_KIND = "linkedin.profile"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local example receiver; do not use with credentials.
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


def page_text(raw_entry: RawEntry) -> str:
    if isinstance(raw_entry.content, bytes):
        return raw_entry.content.decode("utf-8", errors="replace")
    return raw_entry.content


def compact_text(values: list[str]) -> str:
    return " ".join(value.strip() for value in values if value.strip())


def query_text(input: PipelineInput, key: str) -> str:
    if not isinstance(input.query, Mapping):
        return ""
    value = input.query.get(key, "")
    return value.strip() if isinstance(value, str) else ""


def title_name(selector: Selector) -> str:
    title = selector.css("meta[property='og:title']::attr(content), title::text").get(
        ""
    )
    return title.removesuffix(" | LinkedIn").strip()


class LinkedInPeopleSearchExtractor(DefaultExtractor[dict[str, str]]):
    def __init__(self) -> None:
        super().__init__(allowed_domain="linkedin.com")

    async def extract(
        self, input: PipelineInput, raw_entry: RawEntry
    ) -> ExtractionResult[dict[str, str]]:
        selector = Selector(text=page_text(raw_entry))
        people: list[RichEntry[dict[str, str]]] = []
        seen_urls: set[str] = set()
        # Search-result rows have no stable element name or CSS class.  The
        # profile URL is the durable part of their rendered markup, so walk
        # those links directly instead of assuming results are ``li`` nodes.
        for link in selector.xpath("//a[contains(@href, '/in/')]"):
            href = link.attrib.get("href")
            if not href:
                continue
            url = urljoin(raw_entry.url, href).split("?", maxsplit=1)[0]
            if "/in/" not in url or url in seen_urls:
                continue
            seen_urls.add(url)
            name = compact_text(link.css("span[aria-hidden='true']::text").getall())
            if not name:
                name = compact_text(link.css("::text").getall())
            if not name:
                name = link.attrib.get("aria-label", "").strip()
            if name:
                people.append(
                    RichEntry(url=url, data={"name": name, "profile_url": url})
                )
        return ExtractionResult(items=people, tasks=[])


class LinkedInProfileExtractor(DefaultExtractor[dict[str, str]]):
    def __init__(self) -> None:
        super().__init__(allowed_domain="linkedin.com")

    async def extract(
        self, input: PipelineInput, raw_entry: RawEntry
    ) -> ExtractionResult[dict[str, str]]:
        selector = Selector(text=page_text(raw_entry))
        top_card = selector.xpath("//*[contains(@id, 'Topcard')]")
        name = query_text(input, "profile_name")
        if not name:
            name = compact_text(top_card.xpath(".//h2[1]//text()").getall())
        if not name:
            name = compact_text(selector.css("main h1::text, h1::text").getall())
        if not name:
            name = title_name(selector)

        headline = query_text(input, "profile_headline")
        if not headline:
            headline = compact_text(
                top_card.xpath(
                    ".//h2[1]/following::p[normalize-space() "
                    "and not(starts-with(normalize-space(), '·'))][1]//text()"
                ).getall()
            )
        if not headline:
            headline = compact_text(
                selector.css("main .text-body-medium::text").getall()
            )
        if not headline:
            headline = (
                selector.css(
                    "meta[property='og:description']::attr(content), "
                    "meta[name='description']::attr(content)"
                )
                .get("")
                .strip()
            )
        return ExtractionResult(
            items=[
                RichEntry(
                    url=raw_entry.url,
                    data={"name": name, "headline": headline},
                )
            ],
            tasks=[],
        )


WORKERS = {
    SEARCH_KIND: ScraperWorker(
        None, LinkedInPeopleSearchExtractor(), task_kind=SEARCH_KIND
    ),
    PROFILE_KIND: ScraperWorker(
        None, LinkedInProfileExtractor(), task_kind=PROFILE_KIND
    ),
}


async def process_capture(input: RawInput) -> list[RichEntry[Any]]:
    async with Crawler(WORKERS) as crawler:
        return await crawler.run_inputs(input)


class BrowserCapture(BaseModel):
    kind: str
    query: Any = Field(default_factory=dict)
    url: str
    content: str
    content_type: str = "text/html"


@app.post("/captures")
async def capture(capture: BrowserCapture) -> dict[str, Any]:
    items = await process_capture(
        RawInput(
            kind=capture.kind,
            query=capture.query,
            raw_entry=RawEntry(
                url=capture.url,
                content=capture.content,
                content_type=capture.content_type,
            ),
        )
    )
    for item in items:
        print(json.dumps(item.data, ensure_ascii=False, default=str))
    return {"status": "ok", "items": len(items)}
