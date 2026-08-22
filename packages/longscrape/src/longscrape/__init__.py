"""Runtime integrations built on longscrape-core."""

import logging as stdlib_logging

from longscrape_core import *

from longscrape.logging import configure_logging
from longscrape.observability import (
    LoggingObserver,
    OpenTelemetryObserver,
    StructlogObserver,
)
from longscrape.runtime import Flow, FlowExecutor, Worker
from longscrape.runtime.work import JobExecutor, WorkLease, WorkRequest, WorkStore

stdlib_logging.getLogger("longscrape").addHandler(stdlib_logging.NullHandler())

__all__ = [
    "Flow",
    "FlowExecutor",
    "JobExecutor",
    "LoggingObserver",
    "OpenTelemetryObserver",
    "StructlogObserver",
    "WorkLease",
    "WorkRequest",
    "WorkStore",
    "Worker",
    "configure_logging",
]
