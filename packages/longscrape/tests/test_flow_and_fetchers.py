import asyncio
from collections.abc import AsyncIterable, AsyncIterator

from longscrape import (
    Document,
    FetchFailure,
    FetchFailureKind,
    InputUrl,
    Job,
    PipelineContext,
    Record,
    RetryableFetchFailure,
)
from longscrape.browser.context import CURRENT_PAGE
from longscrape.fetchers import (
    BrowserFetcher,
    CachedFetcher,
    HandoffFetcher,
    RetryingFetcher,
)
from longscrape.runtime import Flow
from longscrape.stores import InMemoryDocumentStore
from longscrape_core.protocols import RecordSink


class OneDocumentFetcher:
    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        assert isinstance(job.input, InputUrl)
        yield Document(url=job.input.url, content=b"document")


class OneRecordExtractor:
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record]:
        async for document in documents:
            yield Record(kind=job.kind, data={"url": document.url})


class InMemoryRecordStore:
    def __init__(self) -> None:
        self.records: list[Record] = []

    async def store(self, record: Record) -> None:
        self.records.append(record)

    async def get(self, key: str) -> Record | None:
        return None


def test_flow_builds_record_callables_with_or_without_a_sink() -> None:
    job = Job("article", InputUrl("https://example.com"))
    records_flow = (
        Flow().fetch(OneDocumentFetcher()).extract(OneRecordExtractor()).build()
    )

    async def collect() -> list[Record]:
        return [record async for record in records_flow(job)]  # type: ignore[operator]

    assert [record.data for record in asyncio.run(collect())] == [
        {"url": "https://example.com"}
    ]

    store = InMemoryRecordStore()
    sink_flow = (
        Flow()
        .fetch(OneDocumentFetcher())
        .extract(OneRecordExtractor())
        .consume(RecordSink(store))
        .build()
    )

    async def consume() -> list[Record]:
        return [record async for record in sink_flow(job)]

    assert asyncio.run(consume()) == []
    assert [record.data for record in store.records] == [{"url": "https://example.com"}]


class FlakyFetcher:
    def __init__(self) -> None:
        self.attempts = 0

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        self.attempts += 1
        if self.attempts == 1:
            raise RetryableFetchFailure(FetchFailureKind.NETWORK, "disconnected")
        yield Document(url="https://example.com", content=b"ok")


def test_retrying_fetcher_retries_transient_failure() -> None:
    fetcher = FlakyFetcher()
    retrying = RetryingFetcher(fetcher, max_retries=1)

    async def collect() -> list[Document]:
        job = Job("article", InputUrl("https://example.com"))
        return [document async for document in retrying.fetch(job)]

    assert [document.content for document in asyncio.run(collect())] == [b"ok"]
    assert fetcher.attempts == 2


class CaptchaThenDocumentFetcher:
    def __init__(self) -> None:
        self.attempts = 0

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        self.attempts += 1
        content = b"captcha" if self.attempts == 1 else b"article"
        yield Document(url="https://example.com", content=content)


class RedirectingFetcher:
    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        yield Document(
            url="https://example.com/author/alice/",
            content=b"author",
        )


class RecordingHandoff:
    def __init__(self) -> None:
        self.calls = 0

    async def resolve(
        self,
        *,
        job: Job,
        document: Document,
        failure: FetchFailure,
    ) -> None:
        self.calls += 1


def test_handoff_fetcher_suppresses_blocked_document_and_retries() -> None:
    fetcher = CaptchaThenDocumentFetcher()
    handoff = RecordingHandoff()

    def detector(document: Document, job: Job) -> FetchFailure | None:
        if document.content == b"captcha":
            return FetchFailure(FetchFailureKind.BLOCKED, "captcha", url=document.url)
        return None

    wrapped = HandoffFetcher(fetcher, detector=detector, handoff=handoff)

    async def collect() -> list[Document]:
        job = Job("article", InputUrl("https://example.com"))
        return [document async for document in wrapped.fetch(job)]

    assert [document.content for document in asyncio.run(collect())] == [b"article"]
    assert fetcher.attempts == 2
    assert handoff.calls == 1


class FakeBrowserPage:
    url = "https://example.com/reused"

    def __init__(self) -> None:
        self.closed = False

    async def goto(self, url: str) -> None:
        self.url = url
        return None

    async def content(self) -> str:
        return "<html>reused</html>"

    async def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self) -> None:
        self.created_pages = 0

    async def create_page(self) -> FakeBrowserPage:
        self.created_pages += 1
        return FakeBrowserPage()

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    def register_middleware(self, middleware: object) -> None:
        pass


def test_browser_fetcher_reuses_page_from_pipeline_context() -> None:
    async def collect() -> tuple[list[Document], FakeBrowser, FakeBrowserPage]:
        browser = FakeBrowser()
        page = FakeBrowserPage()
        context = PipelineContext()
        context.set(CURRENT_PAGE, page)
        fetcher = BrowserFetcher(browser, page_mode="reuse")
        documents = [
            document
            async for document in fetcher.fetch(
                Job("article", InputUrl("https://example.com/reused")),
                context,
            )
        ]
        return documents, browser, page

    documents, browser, page = asyncio.run(collect())

    assert [document.url for document in documents] == ["https://example.com/reused"]
    assert browser.created_pages == 0
    assert page.closed is False


def test_cached_fetcher_without_a_fallback_is_read_only() -> None:
    async def collect() -> tuple[list[Document], list[Document]]:
        store = InMemoryDocumentStore()
        cached = Document(url="https://example.com/cached", content=b"cached")
        await store.store(cached)
        fetcher = CachedFetcher(None, store, write=False)

        hit = [
            document
            async for document in fetcher.fetch(
                Job("article", InputUrl("https://example.com/cached"))
            )
        ]
        miss = [
            document
            async for document in fetcher.fetch(
                Job("article", InputUrl("https://example.com/missing"))
            )
        ]
        return hit, miss

    hit, miss = asyncio.run(collect())
    assert [document.content for document in hit] == [b"cached"]
    assert miss == []


def test_cached_fetcher_uses_request_key_when_a_fetch_redirects() -> None:
    async def collect() -> list[Document]:
        store = InMemoryDocumentStore()
        request_url = "https://example.com/author/alice"
        job = Job("author", InputUrl(request_url))
        writer = CachedFetcher(RedirectingFetcher(), store)
        _ = [document async for document in writer.fetch(job)]

        reader = CachedFetcher(None, store, write=False)
        return [document async for document in reader.fetch(job)]

    documents = asyncio.run(collect())

    assert [document.url for document in documents] == [
        "https://example.com/author/alice/"
    ]
