"""Public domain types and pipeline contracts for longscrape."""

from longscrape_core.domain import (
    BrowserHandoffRequired,
    Document,
    FetchFailure,
    FetchFailureKind,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    JobInput,
    JobRequest,
    JsonScalar,
    JsonValue,
    Record,
    RetryableFetchFailure,
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
    "BrowserHandoffRequired",
    "Document",
    "Extractor",
    "FetchFailure",
    "FetchFailureKind",
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
    "RetryableFetchFailure",
    "Transformer",
]
