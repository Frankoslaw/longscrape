"""Public domain types and pipeline contracts for longscrape."""

from longscrape_core._json import JsonScalar, JsonValue
from longscrape_core.context import ContextKey, PipelineContext
from longscrape_core.failures import (
    BrowserHandoffRequired,
    FetchFailure,
    FetchFailureKind,
    RetryableFetchFailure,
)
from longscrape_core.models import (
    Document,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    JobInput,
    JobRequest,
    Record,
)
from longscrape_core.protocols import (
    Extractor,
    Fetcher,
    Transformer,
)

__all__ = [
    "BrowserHandoffRequired",
    "ContextKey",
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
    "JsonScalar",
    "JsonValue",
    "PipelineContext",
    "Record",
    "RetryableFetchFailure",
    "Transformer",
]
