"""Job-agnostic domain values and stage contracts for longscrape."""

from longscrape.core.context import Context, ContextKey
from longscrape.core.failures import (
    HttpStatusError,
    PipelineFailure,
    PipelineStage,
    StageExecutionError,
)
from longscrape.core.models import (
    Document,
    FetchInput,
    InputQuery,
    InputUrl,
    Record,
)
from longscrape.core.pipeline import Extractor, Fetcher, Transformer
from longscrape.utils import JsonScalar, JsonValue

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
