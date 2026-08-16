import logging as stdlib_logging

from longscrape_core import (
    DISCARD_SUBMITTER,
    Document,
    Extractor,
    Fetcher,
    InputDocument,
    InputQuery,
    InputUrl,
    Job,
    JobRequest,
    JobSubmitter,
    Record,
    Transformer,
)
from longscrape_core.ports import DocumentStore, RecordSink, RecordStore

from longscrape.adapters.browser_capture import BrowserCapture, BrowserCaptureServer
from longscrape.adapters.fetchers import CachedFetcher, RateLimitedFetcher
from longscrape.adapters.ratelimit import LeakyBucketRateLimiter, RateLimiter
from longscrape.logging import configure_logging

stdlib_logging.getLogger("longscrape").addHandler(stdlib_logging.NullHandler())

__all__ = [
    "BrowserCapture",
    "BrowserCaptureServer",
    "CachedFetcher",
    "DISCARD_SUBMITTER",
    "Document",
    "DocumentStore",
    "Extractor",
    "Fetcher",
    "InputDocument",
    "InputQuery",
    "InputUrl",
    "Job",
    "JobRequest",
    "JobSubmitter",
    "LeakyBucketRateLimiter",
    "RateLimiter",
    "RateLimitedFetcher",
    "Record",
    "RecordSink",
    "RecordStore",
    "Transformer",
    "configure_logging",
]
