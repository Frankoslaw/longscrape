"""Observe standalone stages and a composed flow.

Run with ``uv run python -m examples.observability``.  OpenTelemetry exporter
configuration is deliberately left to the application.
"""

import asyncio
import logging
from collections.abc import AsyncIterable, AsyncIterator

from longscrape import Context, Document, FetchInput, InputUrl, Record
from longscrape.observability import (
    configure,
    observe_extractor,
    observe_fetch,
    observe_flow,
)
from longscrape.runtime import Flow

logger = logging.getLogger(__name__)


class DemoFetcher:
    async def fetch(self, fetch_input: FetchInput, context: Context) -> Document:
        assert isinstance(fetch_input, InputUrl)
        logger.info("fetching demo document", extra={"url": fetch_input.url})
        return Document(fetch_input.url, b"longscrape observability")


class DemoExtractor:
    def extract(
        self, document: Document, context: Context
    ) -> AsyncIterable[Record[dict[str, str]]]:
        async def records() -> AsyncIterator[Record[dict[str, str]]]:
            logger.info("extracting demo record", extra={"url": document.url})
            yield Record("demo", {"url": document.url})

        return records()


async def main() -> None:
    observer = configure(logging_enabled=True, structlog=True, level=logging.DEBUG)
    flow = observe_flow(
        Flow()
        .fetch(observe_fetch(DemoFetcher(), observer=observer))
        .extract(observe_extractor(DemoExtractor(), observer=observer))
        .build(),
        observer=observer,
        name="demo-flow",
    )
    records = [
        record async for record in flow(InputUrl("https://example.com"), Context())
    ]
    print(records)


if __name__ == "__main__":
    asyncio.run(main())
