"""Job-agnostic domain values and stage contracts for longscrape."""

from longscrape_core._json import JsonScalar, JsonValue
from longscrape_core.context import Context, ContextKey
from longscrape_core.failures import (
    HttpStatusError,
    PipelineFailure,
    PipelineStage,
    StageExecutionError,
)
from longscrape_core.models import (
    Document,
    FetchInput,
    InputQuery,
    InputUrl,
    Record,
)
from longscrape_core.protocols import Extractor, Fetcher, Transformer

__all__ = [
    "Context",
    "ContextKey",
    "Document",
    "Extractor",
    "Fetcher",
    "FetchInput",
    "HttpStatusError",
    "InputQuery",
    "InputUrl",
    "JsonScalar",
    "JsonValue",
    "PipelineFailure",
    "PipelineStage",
    "Record",
    "StageExecutionError",
    "Transformer",
]
