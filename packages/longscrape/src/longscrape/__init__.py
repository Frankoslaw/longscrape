import logging as stdlib_logging

from longscrape.core.domain.pipeline import (
    CachePolicy,
    ExtractionResult,
    FetchRequest,
    PipelineInput,
    RawEntry,
    RawInput,
    RichEntry,
    ScraperTask,
)
from longscrape.core.domain.queue import InMemoryTaskQueue
from longscrape.core.ports.pipeline import (
    DefaultExtractor,
    ExtractorPort,
    FetcherPort,
    RawEntryStore,
)
from longscrape.core.ports.queue import TaskQueue
from longscrape.core.ports.ratelimit import (
    DummyRateLimiter,
    LeakyBucketRateLimiter,
    RateLimiter,
)
from longscrape.core.services.browser_capture import (
    BrowserCapture,
    BrowserCaptureServer,
)
from longscrape.core.services.crawler import Crawler
from longscrape.core.services.reextract import ReExtractor, ReExtractWorker
from longscrape.core.services.worker import ScraperWorker
from longscrape.logging import configure_logging

stdlib_logging.getLogger("longscrape").addHandler(stdlib_logging.NullHandler())

Task = ScraperTask

__all__ = [
    "BrowserCapture",
    "BrowserCaptureServer",
    "CachePolicy",
    "Crawler",
    "DefaultExtractor",
    "DummyRateLimiter",
    "ExtractionResult",
    "ExtractorPort",
    "FetchRequest",
    "FetcherPort",
    "InMemoryTaskQueue",
    "LeakyBucketRateLimiter",
    "PipelineInput",
    "RateLimiter",
    "RawEntry",
    "RawEntryStore",
    "RawInput",
    "ReExtractWorker",
    "ReExtractor",
    "RichEntry",
    "ScraperTask",
    "ScraperWorker",
    "Task",
    "TaskQueue",
    "configure_logging",
]
