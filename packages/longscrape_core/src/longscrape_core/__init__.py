"""Dependency-light values and stage contracts for longscrape."""

from longscrape_core._json import JsonInput, JsonObject, JsonScalar, JsonValue
from longscrape_core.context import ContextKey, PipelineContext
from longscrape_core.failures import Stage, StageError, StageFailure
from longscrape_core.models import (
    Document,
    DocumentRef,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    JobInput,
    Record,
)
from longscrape_core.pipeline import Extractor, Fetcher, Sink, Transformer
from longscrape_core.serialization import job_from_json, job_to_json

__all__ = [
    "ContextKey",
    "Document",
    "DocumentRef",
    "Extractor",
    "Fetcher",
    "InputDocument",
    "InputQuery",
    "InputUrl",
    "Job",
    "JobInput",
    "JsonInput",
    "JsonObject",
    "JsonScalar",
    "JsonValue",
    "PipelineContext",
    "Record",
    "Sink",
    "Stage",
    "StageError",
    "StageFailure",
    "Transformer",
    "job_from_json",
    "job_to_json",
]
