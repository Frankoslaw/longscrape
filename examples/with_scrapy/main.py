"""Run the longscrape-enabled spider through Dramatiq.

Start a Redis instance, then run the worker and submitter from this directory:

    uv run --package longscrape --extra dramatiq dramatiq main
    uv run --package longscrape --extra dramatiq python main.py

The existing project entrypoint is unchanged:

    uv run scrapy crawl quotes
"""

import asyncio
import os

from longscrape import InputUrl, Job, JobRequest, PipelineContext
from longscrape.orchestration import DramatiqApp
from longscrape_scrapy import ScrapyJobRunner
from with_scrapy.spiders.quotes_longscrape import QuotesLongscrapeSpider

KIND = "quotes_longscrape"
app = DramatiqApp.redis(url=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
runner = ScrapyJobRunner.from_scrapy_project()


@app.job(kind=KIND, queue="scrapy")
async def quotes(job: Job, context: PipelineContext) -> None:
    await runner.run(QuotesLongscrapeSpider, job, context)


async def main() -> None:
    await app.submit(JobRequest(KIND, InputUrl("https://quotes.toscrape.com/")))


if __name__ == "__main__":
    asyncio.run(main())
