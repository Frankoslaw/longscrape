import logging as stdlib_logging

from longscrape_core import (
    DISCARD_SUBMITTER,
    Document,
    Extractor,
    Fetcher,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    JobRequest,
    JobSubmitter,
    Record,
    Transformer,
)
from longscrape_core.ports import DocumentStore, RecordSink, RecordStore

from longscrape.logging import configure_logging

stdlib_logging.getLogger("longscrape").addHandler(stdlib_logging.NullHandler())

__all__ = [
    "DISCARD_SUBMITTER",
    "Document",
    "DocumentStore",
    "Extractor",
    "Fetcher",
    "InputDocument",
    "InputQuery",
    "InputUrl",
    "Job",
    "JobRequest",
    "JobSubmitter",
    "Record",
    "RecordSink",
    "RecordStore",
    "Transformer",
    "configure_logging",
]
