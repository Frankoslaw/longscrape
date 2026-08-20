"""Public domain types and pipeline contracts for longscrape."""

from longscrape_core._json import JsonScalar, JsonValue
from longscrape_core.context import ContextKey, PipelineContext
from longscrape_core.failures import (
    HttpStatusError,
    PipelineFailure,
    PipelineStage,
    Recovery,
    RecoveryAction,
    StageExecutionError,
)
from longscrape_core.models import (
    CollisionPolicy,
    Document,
    DocumentInput,
    DocumentRef,
    InputQuery,
    InputUrl,
    Job,
    JobInput,
    JobRequest,
    JobStatus,
    Record,
    RecordRef,
    StoredJob,
)
from longscrape_core.observability import (
    StageObserver,
    observe_extractor,
    observe_fetcher,
    observe_stage,
    observe_transformer,
)
from longscrape_core.protocols import (
    Extractor,
    Fetcher,
    JobQueue,
    JobStore,
    RecoveryPolicy,
    Transformer,
)

__all__ = [
    "ContextKey",
    "Document",
    "DocumentInput",
    "DocumentRef",
    "Extractor",
    "Fetcher",
    "HttpStatusError",
    "InputQuery",
    "InputUrl",
    "Job",
    "JobInput",
    "JobQueue",
    "JobRequest",
    "JobStatus",
    "JobStore",
    "JsonScalar",
    "JsonValue",
    "PipelineContext",
    "PipelineFailure",
    "PipelineStage",
    "Record",
    "RecordRef",
    "Recovery",
    "RecoveryAction",
    "RecoveryPolicy",
    "StageExecutionError",
    "StageObserver",
    "Transformer",
    "observe_extractor",
    "observe_fetcher",
    "observe_stage",
    "observe_transformer",
    "StoredJob",
    "CollisionPolicy",
]
