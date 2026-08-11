from __future__ import annotations

from typing import Any

import scrapy
from longscrape_core import CrawlJob


class JobSpider(scrapy.Spider):
    """Base spider that receives its :class:`CrawlJob` from the worker.

    ``job`` is a normal Scrapy spider keyword argument.  This avoids encoding
    application state into Scrapy's command-line argument convention and keeps
    spiders usable with ``AsyncCrawlerRunner``.
    """

    def __init__(self, *, job: CrawlJob, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.job = job
