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
    CollisionPolicy,
    Document,
    DocumentRef,
    FetchInput,
    InputQuery,
    InputUrl,
    Record,
    RecordRef,
)
from longscrape_core.observability import (
    StageObserver,
    observe_extractor,
    observe_fetcher,
    observe_stage,
    observe_transformer,
)
from longscrape_core.protocols import (
    DocumentStore,
    Extractor,
    Fetcher,
    RecordSink,
    RecordStore,
    Transformer,
)

__all__ = [
    "CollisionPolicy",
    "Context",
    "ContextKey",
    "Document",
    "DocumentRef",
    "DocumentStore",
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
    "RecordRef",
    "RecordSink",
    "RecordStore",
    "StageExecutionError",
    "StageObserver",
    "Transformer",
    "observe_extractor",
    "observe_fetcher",
    "observe_stage",
    "observe_transformer",
]
