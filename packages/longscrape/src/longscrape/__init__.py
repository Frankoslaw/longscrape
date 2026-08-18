import logging as stdlib_logging

from longscrape_core import (
    BrowserHandoffRequired,
    ContextKey,
    Document,
    Extractor,
    Fetcher,
    FetchFailure,
    FetchFailureKind,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    JobRequest,
    PipelineContext,
    Record,
    RetryableFetchFailure,
    Transformer,
)
from longscrape_core.protocols import DocumentStore, RecordSink, RecordStore

from longscrape.logging import configure_logging

stdlib_logging.getLogger("longscrape").addHandler(stdlib_logging.NullHandler())

__all__ = [
    "BrowserHandoffRequired",
    "ContextKey",
    "Document",
    "DocumentStore",
    "Extractor",
    "FetchFailure",
    "FetchFailureKind",
    "Fetcher",
    "InputDocument",
    "InputQuery",
    "InputUrl",
    "Job",
    "JobRequest",
    "PipelineContext",
    "Record",
    "RetryableFetchFailure",
    "RecordSink",
    "RecordStore",
    "Transformer",
    "configure_logging",
]
