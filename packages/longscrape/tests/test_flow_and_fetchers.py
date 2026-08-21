import asyncio
from collections.abc import AsyncIterable, AsyncIterator

from longscrape import (
    CollisionPolicy,
    Document,
    HttpStatusError,
    InputUrl,
    Job,
    PipelineContext,
    PipelineFailure,
    PipelineStage,
    Record,
    RecordRef,
    Recovery,
    RecoveryAction,
    StageExecutionError,
    observe_extractor,
    observe_fetcher,
)
from longscrape.browser.config import BrowserConfig
from longscrape.browser.context import CURRENT_PAGE
from longscrape.browser.manager import BrowserManager
from longscrape.browser.page_store import PageStore
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

    async def put(
        self,
        record: Record,
        *,
        key: str | None = None,
        policy: CollisionPolicy = CollisionPolicy.NEW,
    ) -> RecordRef:
        self.records.append(record)
        return RecordRef("test", str(len(self.records)))

    async def get(self, ref: RecordRef) -> Record:
        raise LookupError(ref.value)

    async def latest(self, key: str) -> RecordRef | None:
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
        .sink(RecordSink(store))
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
            raise TimeoutError("disconnected")
        yield Document(url="https://example.com", content=b"ok")


class RetryPolicy:
    async def decide(self, failure: PipelineFailure) -> Recovery:
        assert failure.stage is PipelineStage.FETCH
        return Recovery(RecoveryAction.RETRY)


def test_retrying_fetcher_retries_transient_failure() -> None:
    fetcher = FlakyFetcher()
    retrying = RetryingFetcher(fetcher, policy=RetryPolicy(), max_retries=1)

    async def collect() -> list[Document]:
        job = Job("article", InputUrl("https://example.com"))
        return [document async for document in retrying.fetch(job)]

    assert [document.content for document in asyncio.run(collect())] == [b"ok"]
    assert fetcher.attempts == 2


class PartialThenFailingFetcher:
    def __init__(self) -> None:
        self.attempts = 0

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        self.attempts += 1
        yield Document(url="https://example.com", content=b"document")
        if self.attempts == 1:
            raise TimeoutError("disconnected")


def test_retrying_fetcher_does_not_emit_a_partial_attempt() -> None:
    fetcher = PartialThenFailingFetcher()
    retrying = RetryingFetcher(fetcher, policy=RetryPolicy(), max_retries=1)

    async def collect() -> list[Document]:
        return [
            document
            async for document in retrying.fetch(
                Job("article", InputUrl("https://example.com"))
            )
        ]

    assert [document.content for document in asyncio.run(collect())] == [b"document"]
    assert fetcher.attempts == 2


class BlockedThenDocumentFetcher:
    def __init__(self) -> None:
        self.attempts = 0

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        self.attempts += 1
        if self.attempts == 1:
            raise HttpStatusError("https://example.com", 403)
        yield Document(url="https://example.com", content=b"article")


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

    async def resolve(self, failure: PipelineFailure) -> None:
        self.calls += 1


class HandoffPolicy:
    async def decide(self, failure: PipelineFailure) -> Recovery:
        assert failure.stage is PipelineStage.FETCH
        return Recovery(RecoveryAction.HANDOFF)


def test_handoff_fetcher_resolves_a_handoff_decision_and_retries() -> None:
    fetcher = BlockedThenDocumentFetcher()
    handoff = RecordingHandoff()
    wrapped = HandoffFetcher(fetcher, policy=HandoffPolicy(), handoff=handoff)

    async def collect() -> list[Document]:
        job = Job("article", InputUrl("https://example.com"))
        return [document async for document in wrapped.fetch(job)]

    assert [document.content for document in asyncio.run(collect())] == [b"article"]
    assert fetcher.attempts == 2
    assert handoff.calls == 1


def test_handoff_fetcher_does_not_emit_a_partial_attempt() -> None:
    fetcher = PartialThenFailingFetcher()
    handoff = RecordingHandoff()
    wrapped = HandoffFetcher(fetcher, policy=HandoffPolicy(), handoff=handoff)

    async def collect() -> list[Document]:
        return [
            document
            async for document in wrapped.fetch(
                Job("article", InputUrl("https://example.com"))
            )
        ]

    assert [document.content for document in asyncio.run(collect())] == [b"document"]
    assert handoff.calls == 1


class LoginThenDocumentFetcher:
    def __init__(self) -> None:
        self.attempts = 0

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        self.attempts += 1
        content = b"login" if self.attempts == 1 else b"article"
        yield Document(url="https://example.com", content=content)


def test_handoff_fetcher_recovers_a_document_detected_login_page() -> None:
    fetcher = LoginThenDocumentFetcher()
    handoff = RecordingHandoff()

    def detector(document: Document, job: Job) -> Exception | None:
        if document.content == b"login":
            return PermissionError("login required")
        return None

    wrapped = HandoffFetcher(
        fetcher,
        policy=HandoffPolicy(),
        handoff=handoff,
        detector=detector,
    )

    async def collect() -> list[Document]:
        job = Job("article", InputUrl("https://example.com"))
        return [document async for document in wrapped.fetch(job)]

    assert [document.content for document in asyncio.run(collect())] == [b"article"]
    assert fetcher.attempts == 2
    assert handoff.calls == 1


class RecordingObserver:
    def __init__(self) -> None:
        self.failures: list[PipelineFailure] = []

    async def on_stage_failed(self, failure: PipelineFailure) -> None:
        self.failures.append(failure)


class FailingExtractor:
    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record]:
        async for _ in documents:
            raise ValueError("cannot parse document")
        if False:
            yield


def test_flow_notifies_an_optional_observer_and_wraps_failures() -> None:
    observer = RecordingObserver()
    flow = (
        Flow(observers=[observer])
        .fetch(OneDocumentFetcher())
        .extract(FailingExtractor())
        .build()
    )

    async def consume() -> None:
        async for _ in flow(Job("article", InputUrl("https://example.com"))):
            pass

    try:
        asyncio.run(consume())
    except StageExecutionError as error:
        assert error.failure.stage is PipelineStage.EXTRACT
        assert isinstance(error.error, ValueError)
        assert str(error.error) == "cannot parse document"
        assert isinstance(error.__cause__, ValueError)
    else:
        raise AssertionError("expected extractor failure")

    assert [(failure.stage, str(failure.error)) for failure in observer.failures] == [
        (PipelineStage.EXTRACT, "cannot parse document")
    ]


class BrokenObserver:
    async def on_stage_failed(self, failure: PipelineFailure) -> None:
        raise RuntimeError("telemetry unavailable")


def test_observer_failure_does_not_replace_pipeline_failure() -> None:
    flow = (
        Flow(observers=[BrokenObserver()])
        .fetch(OneDocumentFetcher())
        .extract(FailingExtractor())
        .build()
    )

    async def consume() -> None:
        async for _ in flow(Job("article", InputUrl("https://example.com"))):
            pass

    try:
        asyncio.run(consume())
    except StageExecutionError as error:
        assert isinstance(error.error, ValueError)
    else:
        raise AssertionError("expected StageExecutionError")


class LifecycleObserver:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def on_stage_started(
        self, stage: PipelineStage, job: Job, context: PipelineContext | None
    ) -> None:
        self.events.append(f"{stage.value}_started")

    async def on_stage_succeeded(
        self, stage: PipelineStage, job: Job, context: PipelineContext | None
    ) -> None:
        self.events.append(f"{stage.value}_succeeded")

    async def on_stage_failed(self, failure: PipelineFailure) -> None:
        self.events.append("failure")


def test_flow_emits_stage_lifecycle_events() -> None:
    observer = LifecycleObserver()
    flow = (
        Flow(observers=[observer])
        .fetch(OneDocumentFetcher())
        .extract(OneRecordExtractor())
        .build()
    )

    async def consume() -> None:
        async for _ in flow(Job("article", InputUrl("https://example.com"))):
            pass

    asyncio.run(consume())

    assert observer.events == [
        "extract_started",
        "fetch_started",
        "fetch_succeeded",
        "extract_succeeded",
    ]


def test_flow_notifies_multiple_observers() -> None:
    first = LifecycleObserver()
    second = LifecycleObserver()
    flow = (
        Flow(observers=[first, second])
        .fetch(OneDocumentFetcher())
        .extract(OneRecordExtractor())
        .build()
    )

    async def consume() -> None:
        async for _ in flow(Job("article", InputUrl("https://example.com"))):
            pass

    asyncio.run(consume())
    assert first.events == second.events


def test_observed_components_work_in_manual_composition() -> None:
    observer = LifecycleObserver()
    job = Job("article", InputUrl("https://example.com"))

    async def consume() -> list[Record]:
        documents = observe_fetcher(OneDocumentFetcher(), observer).fetch(job)
        records = observe_extractor(OneRecordExtractor(), observer).extract(
            documents, job
        )
        return [record async for record in records]

    assert [record.data for record in asyncio.run(consume())] == [
        {"url": "https://example.com"}
    ]
    assert observer.events == [
        "extract_started",
        "fetch_started",
        "fetch_succeeded",
        "extract_succeeded",
    ]


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


class FakeBrowserContext:
    def __init__(self) -> None:
        self.closed = False

    async def new_page(self) -> FakeBrowserPage:
        return FakeBrowserPage()

    async def close(self) -> None:
        self.closed = True


class FakeManagedBrowser:
    def __init__(self) -> None:
        self.contexts: list[FakeBrowserContext] = []

    async def new_context(self, **kwargs: object) -> FakeBrowserContext:
        context = FakeBrowserContext()
        self.contexts.append(context)
        return context

    async def close(self) -> None:
        pass


class FakeBrowserProvider:
    def __init__(self, config: BrowserConfig | None = None) -> None:
        self.browser = FakeManagedBrowser()

    async def start(self) -> None:
        pass

    async def launch_browser(self) -> FakeManagedBrowser:
        return self.browser

    async def close(self) -> None:
        pass


class FakeBrowser:
    def __init__(self) -> None:
        self.created_pages = 0
        self.page_store = PageStore()

    async def create_page(self) -> FakeBrowserPage:
        self.created_pages += 1
        return FakeBrowserPage()

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    def restore_page(self, page_id: str) -> FakeBrowserPage:
        return self.page_store.require(page_id)

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


def test_browser_fetcher_restores_a_page_named_in_job_metadata() -> None:
    async def collect() -> tuple[list[Document], FakeBrowser, FakeBrowserPage]:
        browser = FakeBrowser()
        page = FakeBrowserPage()
        page_id = browser.page_store.put(page)
        fetcher = BrowserFetcher(browser, page_mode="stored")
        documents = [
            document
            async for document in fetcher.fetch(
                Job(
                    "article",
                    InputUrl("https://example.com/restored"),
                    metadata={"browser_page_id": page_id},
                )
            )
        ]
        return documents, browser, page

    documents, browser, page = asyncio.run(collect())

    assert [document.url for document in documents] == ["https://example.com/restored"]
    assert browser.created_pages == 0
    assert page.closed is False


def test_replacing_a_browser_context_invalidates_stored_pages() -> None:
    async def run() -> None:
        manager = BrowserManager(FakeBrowserProvider(), BrowserConfig())
        await manager.start()
        page = await manager.create_page()
        page_id = manager.store_page(page)
        await manager.replace_context(storage_state={})
        assert page.closed is True
        try:
            manager.restore_page(page_id)
        except LookupError:
            pass
        else:
            raise AssertionError("expected the stored page to be invalidated")
        await manager.stop()

    asyncio.run(run())


def test_cached_fetcher_without_a_fallback_is_read_only() -> None:
    async def collect() -> tuple[list[Document], list[Document]]:
        store = InMemoryDocumentStore()
        cached = Document(url="https://example.com/cached", content=b"cached")
        job = Job("article", InputUrl("https://example.com/cached"))
        await store.put(cached, key=job.hash)
        fetcher = CachedFetcher(None, store, write=False)

        hit = [document async for document in fetcher.fetch(job)]
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
