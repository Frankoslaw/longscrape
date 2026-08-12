# longscrape

`longscrape` provides optional direct fetcher implementations for the
small `longscrape-core` interfaces. It has no worker, crawler, rate-limiter,
or extraction orchestration API.

## Direct HTTP flow

The application composes each stage explicitly. This example fetches one job,
extracts a record, applies two transformers, and persists the output:

```python
from longscrape import HttpxFetcher
from longscrape_core import (
    Document,
    Extractor,
    InMemoryJobQueue,
    InMemoryRecordStore,
    InputUrl,
    Job,
    JobQueue,
    Record,
    Transformer,
)
from parsel import Selector


class CompanyExtractor(Extractor):
    async def extract(
        self, job: Job, document: Document, queue: JobQueue
    ) -> list[Record]:
        selector = Selector(text=document.text)
        return [
            Record(
                kind="company",
                source_url=document.url,
                document=document,
                data={"name": selector.css("h1::text").get("")},
            )
        ]


class StripCompanyName(Transformer):
    async def transform(self, job: Job, record: Record) -> list[Record]:
        return [
            Record(
                kind=record.kind,
                source_url=record.source_url,
                document=record.document,
                data={**record.data, "name": str(record.data["name"]).strip()},
            )
        ]


class DropUnnamedCompanies(Transformer):
    async def transform(self, job: Job, record: Record) -> list[Record]:
        return [record] if record.data["name"] else []


queue = InMemoryJobQueue()
records = InMemoryRecordStore()
job = Job(kind="company", input=InputUrl("https://example.com"))

async with HttpxFetcher() as fetcher:
    document = await fetcher.fetch(job)
    extracted = await CompanyExtractor().extract(job, document, queue)
    for transformer in (StripCompanyName(), DropUnnamedCompanies()):
        extracted = [
            output
            for record in extracted
            for output in await transformer.transform(job, record)
        ]
    for record in extracted:
        await records.save(record)
```

An extractor can enqueue discovered work directly with `await queue.enqueue(...)`.
Consumers always use `await queue.dequeue("supported-kind")`, so unrelated
backends cannot claim that work.

## Minimal Scrapy integration

Keep native Scrapy items and make only two spider changes: inherit `JobSpider`
and replace `start()` with `start_job()`. Add `source_url` to yielded items so
the optional `LongscrapePipeline` can convert them to core records.

```python
import scrapy
from longscrape_core import InputUrl
from longscrape_scrapy import JobSpider


class CompanySpider(JobSpider):
    name = "company"

    async def start_job(self):
        job = self.job
        if job is None or not isinstance(job.input, InputUrl):
            raise TypeError("CompanySpider requires an InputUrl job")
        yield scrapy.Request(job.input.url, callback=self.parse)

    def parse(self, response):
        yield {
            "source_url": response.url,
            "name": response.css("h1::text").get(),
        }
```

Configure `CrawlService.from_project(queue, record_store=store, transformers=[...])`
to install `LongscrapePipeline`. Calling the spider with `scrapy crawl` remains
safe: `JobSpider` has no job, logs a warning, and exits without queued input.

Browser backends are available as optional extras:

- `PlaywrightFetcher` / `PlaywrightManager`: `longscrape[playwright]`
- `StealthFetcher` / `StealthPlaywrightManager`: `longscrape[stealth]`
- `PatchrightFetcher` / `PatchrightManager`: `longscrape[patchright]`

All browser fetchers accept `InputUrl` jobs and return core `Document`s.
Managers may be given `ContentTypeBlocklist`, `URLBlocklist`, or `URLCacher`
route handlers through `route_handlers=`.

`longscrape.capture.create_capture_app()` is an optional FastAPI receiver
for browser-extension captures. It creates a `Job(InputDocument(...))` and
passes it to an application-supplied processor. MongoDB stores are available
from `longscrape.mongodb` with the `mongodb` extra.
