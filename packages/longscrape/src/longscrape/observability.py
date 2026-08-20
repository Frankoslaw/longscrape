"""Optional structured logging and OpenTelemetry observers.

This module is safe to import without optional dependencies.  The individual
adapters explain which extra is required when they are instantiated.
"""

from __future__ import annotations

import logging
from contextlib import ExitStack
from contextvars import ContextVar
from typing import Any

from longscrape_core import Job, PipelineContext, PipelineFailure, PipelineStage

from longscrape.logging import get_logger


def _job_fields(job: Job) -> dict[str, str | None]:
    return {
        "job_id": str(job.id),
        "root_id": str(job.root_id),
        "parent_id": str(job.parent_id) if job.parent_id else None,
        "job_kind": job.kind,
        "worker_id": job.worker_id,
    }


class LoggingObserver:
    """Lifecycle logs using the standard library's logging configuration."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or get_logger("pipeline")

    async def on_job_started(self, job: Job, context: PipelineContext | None) -> None:
        self._logger.info("job started: %s", _job_fields(job))

    async def on_job_succeeded(self, job: Job, context: PipelineContext | None) -> None:
        self._logger.info("job succeeded: %s", _job_fields(job))

    async def on_stage_started(
        self, stage: PipelineStage, job: Job, context: PipelineContext | None
    ) -> None:
        self._logger.debug("stage started: stage=%s %s", stage.value, _job_fields(job))

    async def on_stage_succeeded(
        self, stage: PipelineStage, job: Job, context: PipelineContext | None
    ) -> None:
        self._logger.debug(
            "stage succeeded: stage=%s %s", stage.value, _job_fields(job)
        )

    async def on_stage_failed(self, failure: PipelineFailure) -> None:
        self._logger.error(
            "pipeline failed: stage=%s error_type=%s error=%s %s",
            failure.stage.value,
            type(failure.error).__name__,
            failure.error,
            _job_fields(failure.job),
            exc_info=(type(failure.error), failure.error, failure.error.__traceback__),
        )


class StructlogObserver:
    """Structured JSON-friendly events; requires ``longscrape[structlog]``."""

    def __init__(self, logger: Any | None = None) -> None:
        try:
            import structlog
        except ImportError as error:  # pragma: no cover - environment dependent
            raise ImportError(
                "Structlog observability requires the 'longscrape[structlog]' extra"
            ) from error
        self._logger = logger or structlog.get_logger("longscrape.pipeline")

    async def on_job_started(self, job: Job, context: PipelineContext | None) -> None:
        self._logger.info("job_started", **_job_fields(job))

    async def on_job_succeeded(self, job: Job, context: PipelineContext | None) -> None:
        self._logger.info("job_succeeded", **_job_fields(job))

    async def on_stage_started(
        self, stage: PipelineStage, job: Job, context: PipelineContext | None
    ) -> None:
        self._logger.debug("stage_started", stage=stage.value, **_job_fields(job))

    async def on_stage_succeeded(
        self, stage: PipelineStage, job: Job, context: PipelineContext | None
    ) -> None:
        self._logger.debug("stage_succeeded", stage=stage.value, **_job_fields(job))

    async def on_stage_failed(self, failure: PipelineFailure) -> None:
        self._logger.error(
            "pipeline_failed",
            stage=failure.stage.value,
            error_type=type(failure.error).__name__,
            error=str(failure.error),
            exc_info=(
                type(failure.error),
                failure.error,
                failure.error.__traceback__,
            ),
            **_job_fields(failure.job),
        )


class OpenTelemetryObserver:
    """Creates nested job/stage spans in the current OpenTelemetry context.

    Configure an exporter in the application before creating the observer. The
    active context is retained while a job is running, allowing child-job
    submission and HTTP instrumentation to attach to the same trace.
    """

    def __init__(self, tracer: Any | None = None) -> None:
        try:
            from opentelemetry import trace
        except ImportError as error:  # pragma: no cover - environment dependent
            raise ImportError(
                "OpenTelemetry observability requires the 'longscrape[otel]' extra"
            ) from error
        self._trace = trace
        self._tracer = tracer or trace.get_tracer("longscrape")
        self._jobs: ContextVar[ExitStack | None] = ContextVar(
            "longscrape_otel_job", default=None
        )
        self._stages: ContextVar[list[ExitStack]] = ContextVar(
            "longscrape_otel_stages", default=[]
        )

    async def on_job_started(self, job: Job, context: PipelineContext | None) -> None:
        stack = ExitStack()
        span = stack.enter_context(
            self._tracer.start_as_current_span(f"job {job.kind}")
        )
        span.set_attributes(
            {
                f"longscrape.{key}": value
                for key, value in _job_fields(job).items()
                if value is not None
            }
        )
        self._jobs.set(stack)
        self._stages.set([])

    async def on_job_succeeded(self, job: Job, context: PipelineContext | None) -> None:
        stack = self._jobs.get()
        if stack is not None:
            stack.close()
        self._jobs.set(None)
        self._stages.set([])

    async def on_stage_started(
        self, stage: PipelineStage, job: Job, context: PipelineContext | None
    ) -> None:
        stack = ExitStack()
        span = stack.enter_context(
            self._tracer.start_as_current_span(f"{stage.value} {job.kind}")
        )
        span.set_attribute("longscrape.stage", stage.value)
        spans = [*self._stages.get(), stack]
        self._stages.set(spans)

    async def on_stage_succeeded(
        self, stage: PipelineStage, job: Job, context: PipelineContext | None
    ) -> None:
        spans = self._stages.get()
        if spans:
            spans[-1].close()
            self._stages.set(spans[:-1])

    async def on_stage_failed(self, failure: PipelineFailure) -> None:
        span = self._trace.get_current_span()
        span.record_exception(failure.error)
        span.set_status(
            self._trace.Status(self._trace.StatusCode.ERROR, str(failure.error))
        )
        for stack in reversed(self._stages.get()):
            stack.close()
        self._stages.set([])
        job = self._jobs.get()
        if job is not None:
            job.close()
        self._jobs.set(None)
