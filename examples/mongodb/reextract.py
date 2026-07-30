import asyncio
import os

from parsel import Selector

from longscrape import (
    DefaultExtractor,
    ExtractionResult,
    PipelineInput,
    RawEntry,
    ReExtractor,
    ReExtractWorker,
    RichEntry,
)
from longscrape.adapters import PyMongoRawEntryStore


class CountryExtractor(DefaultExtractor[str]):
    def __init__(self) -> None:
        super().__init__(allowed_domain="www.scrapethissite.com")

    async def extract(
        self, input: PipelineInput, raw_entry: RawEntry
    ) -> ExtractionResult[str]:
        selector = Selector(text=raw_entry.content)
        countries = [
            RichEntry(url=raw_entry.url, data=name.strip())
            for name in selector.css(".country-name::text").getall()
        ]
        return ExtractionResult(items=countries, tasks=[])


async def main() -> None:
    raw_entries = PyMongoRawEntryStore(
        os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    )
    await raw_entries.start()
    try:
        countries = await ReExtractor(
            raw_entries,
            [ReExtractWorker(CountryExtractor(), task_kind="countries")],
        ).run()
    finally:
        await raw_entries.stop()

    for country in countries[:5]:
        print(country.data)


if __name__ == "__main__":
    asyncio.run(main())
