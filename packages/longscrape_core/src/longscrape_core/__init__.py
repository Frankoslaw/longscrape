"""Public domain types and pipeline contracts for longscrape."""

from longscrape_core.domain import (
    Document,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    JobInput,
    JobRequest,
    JsonScalar,
    JsonValue,
    Record,
)
from longscrape_core.ports import (
    DISCARD_SUBMITTER,
    Extractor,
    Fetcher,
    JobSubmitter,
    NullJobSubmitter,
    Transformer,
)

__all__ = [
    "DISCARD_SUBMITTER",
    "Document",
    "Extractor",
    "Fetcher",
    "InputDocument",
    "InputQuery",
    "InputUrl",
    "Job",
    "JobInput",
    "JobRequest",
    "JobSubmitter",
    "JsonScalar",
    "JsonValue",
    "NullJobSubmitter",
    "Record",
    "Transformer",
]
