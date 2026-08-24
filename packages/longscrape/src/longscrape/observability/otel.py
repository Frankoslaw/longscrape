"""OpenTelemetry event sink; imported only when configured."""

from contextlib import ExitStack
from contextvars import ContextVar
from typing import Any

from longscrape.observability.base import Event


class OpenTelemetrySink:
    def __init__(self, tracer: Any | None = None) -> None:
        try:
            from opentelemetry import trace
        except ImportError as error:  # pragma: no cover
            raise ImportError(
                "OpenTelemetry observation requires 'longscrape[otel]'"
            ) from error
        self._trace = trace
        self._tracer = tracer or trace.get_tracer("longscrape")
        self._spans: ContextVar[dict[str, ExitStack]] = ContextVar(
            "longscrape_otel_spans", default={}
        )

    def emit(self, event: Event) -> None:
        spans = dict(self._spans.get())
        if event.kind == "scope.started":
            stack = ExitStack()
            stack.enter_context(
                self._tracer.start_as_current_span(
                    event.name, attributes=dict(event.attributes)
                )
            )
            spans[event.scope_id] = stack
            self._spans.set(spans)
            return
        stack = spans.pop(event.scope_id, None)
        self._spans.set(spans)
        if stack is None:
            return
        span = self._trace.get_current_span()
        if event.error is not None:
            span.record_exception(event.error)
            span.set_status(
                self._trace.Status(self._trace.StatusCode.ERROR, str(event.error))
            )
        stack.close()
