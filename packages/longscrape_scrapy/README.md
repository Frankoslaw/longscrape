# longscrape-scrapy

`longscrape-scrapy` runs initial core `Job`s as normal in-process Scrapy
crawls. It owns no durable state: applications supply a `JobQueue` and may
drain it themselves or use `CrawlService`.

- `JobSpider` is a normal `scrapy.Spider` with an optional `Job` argument.
  Override `start_job()` for queued execution. Without a job, its default
  `start()` logs a warning and exits safely under `scrapy crawl`.
- `LongscrapePipeline` leaves native Scrapy items intact, then converts them at
  the pipeline boundary to core `Record`s, applies configured transformers,
  and saves them to a `RecordStore`.
- `InMemoryJobQueue` is the core FIFO queue for initial jobs only.

Items processed by `LongscrapePipeline` need a non-empty `source_url` field.

```python
from longscrape_core import InMemoryJobQueue, InputUrl, Job
from longscrape_scrapy import CrawlService

queue = InMemoryJobQueue()
await queue.enqueue(Job(kind="quotes", input=InputUrl("https://example.com")))
service = CrawlService.from_project(queue, record_store=record_store)
await service.run_once("quotes")
```
