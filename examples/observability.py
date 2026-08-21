"""Configure stdlib, Structlog, and OpenTelemetry observability for one flow.

Run from the repository root:

    uv run --package longscrape --extra structlog --extra otel \
        python -m examples.observability --structlog --otel

The demo emits standard-library messages from every stage,
pretty Structlog events for the same user-code actions, and nested spans to
OpenTelemetry's console exporter. Replace that exporter with OTLP in production
to send traces to Jaeger, Tempo, or another compatible backend.
"""

import argparse
import asyncio
import logging
from collections.abc import AsyncIterable, AsyncIterator
from typing import Protocol

from longscrape import (
    Document,
    InputUrl,
    Job,
    LoggingObserver,
    PipelineContext,
    Record,
    observe_extractor,
    observe_fetcher,
    observe_transformer,
)
from longscrape.logging import configure_logging, get_logger
from longscrape.runtime import Flow

STRUCTLOG_HELP = (
    "enable or disable pretty Structlog events (requires longscrape[structlog])"  # noqa: E501
)
OTEL_HELP = "enable or disable OpenTelemetry console spans (requires longscrape[otel])"  # noqa: E501


class EventLogger(Protocol):
    def info(self, event: str, /, **fields: object) -> None: ...


class DemoFetcher:
    def __init__(self, event_logger: EventLogger | None = None) -> None:
        self._logger = get_logger(__name__)
        self._event_logger = event_logger

    async def fetch(
        self, job: Job, context: PipelineContext | None = None
    ) -> AsyncIterator[Document]:
        assert isinstance(job.input, InputUrl)
        self._logger.info("requesting demo document: url=%s", job.input.url)
        if self._event_logger is not None:
            self._event_logger.info("fetching_demo_document", url=job.input.url)
        yield Document(url=job.input.url, content=b"longscrape observability")


class DemoExtractor:
    def __init__(self, event_logger: EventLogger | None = None) -> None:
        self._logger = get_logger(__name__)
        self._event_logger = event_logger

    async def extract(
        self,
        documents: AsyncIterable[Document],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record]:
        async for document in documents:
            self._logger.info("extracting demo record: url=%s", document.url)
            if self._event_logger is not None:
                self._event_logger.info("extracting_demo_record", url=document.url)
            yield Record(kind="page", data={"url": document.url})


class DemoTransformer:
    def __init__(self, event_logger: EventLogger | None = None) -> None:
        self._logger = get_logger(__name__)
        self._event_logger = event_logger

    async def transform(
        self,
        records: AsyncIterable[Record],
        job: Job,
        context: PipelineContext | None = None,
    ) -> AsyncIterator[Record]:
        async for record in records:
            self._logger.info("enriching demo record: url=%s", record.data["url"])
            if self._event_logger is not None:
                self._event_logger.info("enriching_demo_record", url=record.data["url"])
            yield Record(kind=record.kind, data={**record.data, "observed": True})


class DemoSink:
    def __init__(self, event_logger: EventLogger | None = None) -> None:
        self._logger = get_logger(__name__)
        self._event_logger = event_logger

    async def sink(
        self,
        records: AsyncIterable[Record],
        job: Job,
        context: PipelineContext | None = None,
    ) -> None:
        async for record in records:
            self._logger.info("saving demo record: url=%s", record.data["url"])
            if self._event_logger is not None:
                self._event_logger.info("saving_demo_record", url=record.data["url"])
            print(f"saved record: {record.data}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--default-logging",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable or disable stdlib logging and LoggingObserver (default: enabled)",
    )
    parser.add_argument(
        "--structlog",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=STRUCTLOG_HELP,
    )
    parser.add_argument(
        "--otel",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=OTEL_HELP,
    )
    parser.add_argument(
        "--manual",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="manually compose decorated fetch, extract, transform, and sink stages",
    )
    return parser.parse_args()


def configure_structlog() -> EventLogger:
    import structlog

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    )
    return structlog.get_logger("example.user_code")


def configure_tracing() -> None:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: "longscrape-observability-example"})
    )
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)


async def main() -> None:
    args = parse_args()
    observers = []
    event_logger: EventLogger | None = None

    if args.default_logging:
        configure_logging(level=logging.DEBUG)
        observers.append(LoggingObserver())
    if args.structlog:
        from longscrape import StructlogObserver

        event_logger = configure_structlog()
        observers.append(StructlogObserver())
    if args.otel:
        from longscrape import OpenTelemetryObserver

        configure_tracing()
        observers.append(OpenTelemetryObserver())
    if not observers:
        raise SystemExit(
            "Enable --default-logging, --structlog, or --otel to observe the flow"
        )

    job = Job("page", InputUrl("https://example.com"))
    fetcher = DemoFetcher(event_logger)
    extractor = DemoExtractor(event_logger)
    transformer = DemoTransformer(event_logger)
    sink = DemoSink(event_logger)
    if args.manual:
        documents = observe_fetcher(fetcher, *observers).fetch(job)
        records = observe_extractor(extractor, *observers).extract(documents, job)
        enriched = observe_transformer(transformer, *observers).transform(records, job)
        await sink.sink(enriched, job)
        return

    flow = (
        Flow(observers=observers)
        .fetch(fetcher)
        .extract(extractor)
        .transform(transformer)
        .sink(sink)
        .build()
    )
    async for _ in flow(job):
        pass


if __name__ == "__main__":
    asyncio.run(main())
