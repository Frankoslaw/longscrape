"""Scrape country names once and retain the raw response in MongoDB.

Start MongoDB with ``docker compose -f compose.dev.yml up -d``. Run this with
``uv run --extra mongodb python examples/simple_mongodb.py``.
"""

import asyncio
import os

from parsel import Selector

from longscrape import (
    Crawler,
    DefaultExtractor,
    ExtractionResult,
    RawEntry,
    RichEntry,
    ScraperWorker,
    Task,
)
from longscrape.adapters import HttpxFetcher, HttpxManager, PyMongoRawEntryStore

URL = "https://www.scrapethissite.com/pages/simple/"


class CountryExtractor(DefaultExtractor[str]):
    def __init__(self) -> None:
        super().__init__(allowed_domain="www.scrapethissite.com")

    async def extract(self, task: Task, raw_entry: RawEntry) -> ExtractionResult[str]:
        selector = Selector(text=raw_entry.content)
        countries = [
            RichEntry(url=raw_entry.url, data=name.strip())
            for name in selector.css(".country-name::text").getall()
        ]
        return ExtractionResult(items=countries, tasks=[])


async def main() -> None:
    http = HttpxManager()
    raw_entries = PyMongoRawEntryStore(
        os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    )
    async with Crawler(
        {
            "countries": ScraperWorker(
                HttpxFetcher(http, base_domain="www.scrapethissite.com"),
                CountryExtractor(),
                raw_entry_store=raw_entries,
            )
        },
        resources=[http, raw_entries],
    ) as crawler:
        countries = await crawler.run(Task(kind="countries", query=URL))
        for country in countries[:5]:
            print(country.data)


if __name__ == "__main__":
    asyncio.run(main())
