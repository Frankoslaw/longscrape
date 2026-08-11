# longscrape-scrapy

`longscrape-scrapy` is the thin execution layer between `longscrape-core` jobs
and Scrapy. It deliberately owns no durable state: callers provide a
`JobQueue`, and `CrawlService` runs its jobs as bounded, in-process Scrapy
project crawls.

The package is intentionally small:

- `InMemoryJobQueue`: FIFO queue with pending-job de-duplication;
- `CrawlService`: a bounded asyncio worker that resolves `CrawlJob.kind`
  through Scrapy's project spider loader and runs complete project crawls; and
- `JobSpider`: receives a typed `CrawlJob` through Scrapy's normal keyword
  argument mechanism; and
- `RecordSinkPipeline`: sends `longscrape-core` `SourceRecord` items to an
  application-provided `RecordSink`.

The included example starts one asyncio process and runs at most two Scrapy
crawls at a time. It still loads project settings, so spider settings,
middleware, extensions, item pipelines and feed exports behave as they do for
`scrapy crawl`:

```bash
uv run python examples/with_scrapy/run_jobs.py
```

`CrawlService.from_project()` also configures Scrapy logging and emits its
startup information. Pressing Ctrl+C stops active crawlers through Scrapy's
runner before the worker exits.

The example enqueues three `CrawlJob`s in code: two `quotes` jobs with distinct
contexts, proving that the same spider can be run repeatedly, and one `books`
job. A job kind is the project spider name.

```python
class QuotesSpider(JobSpider):
    name = "quotes"

    async def start(self):
        yield scrapy.Request(self.job.query["url"])
```

To persist Scrapy items or `SourceRecord`s, pass a process-owned core sink when
constructing the project service. Existing project pipelines remain enabled.
For ordinary Scrapy items, the pipeline uses their `source_url` field and item
data to create a `SourceRecord`:

```python
service = CrawlService.from_project(queue, record_sink=sink)
```

## Deliberate next steps

Keep the next additions behind the existing `JobQueue` protocol: a durable
queue adapter with job claiming/acknowledgement, retry policy, and scheduling.
Then migrate legacy producers to enqueue `CrawlJob`; keep browser capture in
`longscrape-neo` and enqueue its captured results or follow-up jobs rather than
teaching this package about Playwright.
