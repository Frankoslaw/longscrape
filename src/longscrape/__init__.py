import logging as stdlib_logging

from longscrape.core.doamin.pipeline import (
    ExtractionResult,
    RawEntry,
    RichEntry,
    ScraperTask,
)
from longscrape.core.doamin.queue import InMemoryTaskQueue
from longscrape.core.ports.pipeline import DefaultExtractor, ExtractorPort, FetcherPort
from longscrape.core.ports.queue import TaskQueue
from longscrape.core.services.worker import ScraperWorker
from longscrape.logging import configure_logging

stdlib_logging.getLogger("longscrape").addHandler(stdlib_logging.NullHandler())

Task = ScraperTask

__all__ = [
    "DefaultExtractor",
    "ExtractionResult",
    "ExtractorPort",
    "FetcherPort",
    "InMemoryTaskQueue",
    "RawEntry",
    "RichEntry",
    "ScraperTask",
    "ScraperWorker",
    "Task",
    "TaskQueue",
    "configure_logging",
]
