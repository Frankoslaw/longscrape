import asyncio
from collections.abc import AsyncIterable, AsyncIterator

from longscrape import Context, Document, FetchInput, InputUrl, Record
from longscrape.runtime import Flow


class Fetch:
    async def fetch(self, fetch_input: FetchInput, context: Context) -> Document:
        assert isinstance(fetch_input, InputUrl)
        return Document(fetch_input.url, b"body")


class Extract:
    async def _records(self) -> AsyncIterator[Record[str]]:
        yield Record("example", "value")

    def extract(
        self, document: Document, context: Context
    ) -> AsyncIterable[Record[str]]:
        return self._records()


def test_flow_is_pure_input_and_context_composition() -> None:
    async def run() -> list[Record[str]]:
        flow = Flow().fetch(Fetch()).extract(Extract()).build()
        return [
            record async for record in flow(InputUrl("https://example.com"), Context())
        ]

    records = asyncio.run(run())
    assert [(record.kind, record.data) for record in records] == [("example", "value")]
