# longscrape-scrapy

`longscrape-scrapy` runs initial core `Job`s as normal in-process Scrapy
crawls. It owns no durable state: applications supply a `JobQueue` and may
drain it themselves or use `CrawlService`.

- `JobSpider` is a normal `scrapy.Spider` with an optional `Job` argument.
  Override `start_job()` for queued execution. Without a job, its default
  `start()` logs a warning and exits safely under `scrapy crawl`.
- `LongscrapePipeline` leaves native Scrapy items intact, then extracts core
  `Record`s at the pipeline boundary, applies configured transformers, and
  sends them to a sink. By default it combines `ScrapyItemExtractor` with
  `RecordStoreSink(record_store)`.
- `InMemoryJobQueue` is the core FIFO queue for initial jobs only.

Items processed by `LongscrapePipeline` need a non-empty `source_url` field.

`JobSpider` exposes `initial_url` and `urls`; the latter is filled from all
scheduled requests and received responses. `LongscrapeRequest` and
`LongscrapeResponse` preserve job/document context. For an `InputDocument`
job, `JobSpider.start()` creates an in-memory response and invokes `parse()`,
so normal Scrapy parsing code can run without a network request.

`UrlCrawler` turns an `InputUrl` response into a core `Record` with the fetched
document attached. `IdentityCrawler` turns `InputDocument` or `InputQuery`
jobs directly into records, making existing Scrapy pipelines reusable for
already-acquired longscrape inputs.

## Custom pipeline adapters

Use `ItemExtractor` to adapt items into zero or more core records, and
`RecordSink` to deliver each record. This makes standalone extraction and
storage components usable within a normal Scrapy pipeline:

```python
from longscrape_scrapy import LongscrapePipeline, RecordStoreSink

pipeline = LongscrapePipeline(
    transformers=[...],
    extractor=my_item_extractor,
    sink=RecordStoreSink(record_store),
)
```

Add `LongscrapePipeline` (or a project-specific subclass that constructs its
sink) to Scrapy's `ITEM_PIPELINES` after normal item pipelines. When Scrapy
constructs it, provide instances with `LONGSCRAPE_ITEM_EXTRACTOR` and
`LONGSCRAPE_RECORD_SINK`; the default item extractor and
`LONGSCRAPE_RECORD_STORE` remain available for the common case.

```python
from longscrape_core import InMemoryJobQueue, InputUrl, Job
from longscrape_scrapy import CrawlService

queue = InMemoryJobQueue()
await queue.enqueue(Job(kind="quotes", input=InputUrl("https://example.com")))
service = CrawlService.from_project(queue)
await service.run_once("quotes")
```
