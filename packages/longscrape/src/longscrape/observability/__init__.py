"""Optional logging and tracing for longscrape stages and executions."""

import logging as stdlib_logging

from longscrape.observability.base import (
    NOOP,
    Event,
    EventSink,
    Observer,
    Scalar,
    Scope,
    current_scope,
    get_observer,
    observe_extractor,
    observe_fetch,
    observe_flow,
    observe_job,
    observe_transformer,
    set_observer,
)
from longscrape.observability.logging import LoggingSink, configure_logging, get_logger


def configure(
    *,
    logging_enabled: bool = True,
    structlog: bool = False,
    otel: bool = False,
    level: int = stdlib_logging.INFO,
) -> Observer:
    """Configure and return the process-default observer.

    Exporter/provider configuration remains the application's responsibility.
    """
    sinks: list[EventSink] = []
    if logging_enabled:
        sinks.append(LoggingSink())
        configure_logging(level=level)
    if structlog:
        from longscrape.observability.structlog import StructlogSink

        sinks.append(StructlogSink())
    if otel:
        from longscrape.observability.otel import OpenTelemetrySink

        sinks.append(OpenTelemetrySink())
    return set_observer(Observer(tuple(sinks)))


__all__ = [
    "NOOP",
    "Event",
    "EventSink",
    "LoggingSink",
    "Observer",
    "Scalar",
    "Scope",
    "configure",
    "configure_logging",
    "current_scope",
    "get_logger",
    "get_observer",
    "observe_extractor",
    "observe_fetch",
    "observe_flow",
    "observe_job",
    "observe_transformer",
    "set_observer",
]
