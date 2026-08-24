import asyncio
from collections.abc import AsyncIterable, AsyncIterator

from longscrape import Context, Document, FetchInput, InputUrl, Record
from longscrape.observability import Event, Observer, observe_extractor, observe_fetch


class Events:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        self.events.append(event)


class Fetch:
    async def fetch(self, fetch_input: FetchInput, context: Context) -> Document:
        assert isinstance(fetch_input, InputUrl)
        return Document(fetch_input.url, b"body", status=201)


class Extract:
    async def _records(self) -> AsyncIterator[Record[str]]:
        yield Record("example", "value")

    def extract(
        self, document: Document, context: Context
    ) -> AsyncIterable[Record[str]]:
        return self._records()


def test_stage_observers_emit_safe_input_and_output_summaries() -> None:
    async def run() -> None:
        events = Events()
        observer = Observer((events,))
        document = await observe_fetch(Fetch(), observer=observer).fetch(
            InputUrl("https://example.com"), Context()
        )
        records = observe_extractor(Extract(), observer=observer).extract(
            document, Context()
        )
        assert [record async for record in records]
        assert [event.kind for event in events.events] == [
            "scope.started",
            "scope.succeeded",
            "scope.started",
            "scope.succeeded",
        ]
        assert events.events[1].attributes["output.status"] == 201
        assert events.events[3].attributes["output.record_count"] == 1

    asyncio.run(run())
