import logging as stdlib_logging

from longscrape_core import (
    DISCARD_SUBMITTER,
    BrowserHandoffRequired,
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
    JobSubmitter,
    Record,
    RetryableFetchFailure,
    Transformer,
)
from longscrape_core.ports import DocumentStore, RecordSink, RecordStore

from longscrape.logging import configure_logging

stdlib_logging.getLogger("longscrape").addHandler(stdlib_logging.NullHandler())

__all__ = [
    "DISCARD_SUBMITTER",
    "BrowserHandoffRequired",
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
    "JobSubmitter",
    "Record",
    "RetryableFetchFailure",
    "RecordSink",
    "RecordStore",
    "Transformer",
    "configure_logging",
]
