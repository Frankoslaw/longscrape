# longscrape with Scrapy

Run the example from the repository root:

```bash
docker compose -f compose.dev.yml up -d mongodb
uv run python examples/with_scrapy/main.py
```

Records persist to the `longscrape` database exposed by `compose.dev.yml`, in
MongoDB collections named `records_quotes`, `records_url`, and
`records_identity`, and `records_books`. `MongoRecordPipeline` owns this
connection at pipeline priority 1000, after project normalization. The default
connection is `mongodb://localhost:27017`; set `LONGSCRAPE_MONGODB_URI` to use
another MongoDB instance.

It queues four jobs that demonstrate the supported styles:

- `QuotesSpider` uses `LongscrapeRequest` and performs idiomatic Scrapy parsing
  into `QuoteItem` objects, following each next-page link. When launched with
  `scrapy crawl quotes`, it falls back to its normal `start_urls` value instead
  of requiring a longscrape job.
- `UrlDocumentSpider` inherits `UrlCrawler`; it fetches an `InputUrl` and emits
  a native `LongscrapeDocumentItem` with the response document attached.
- `IdentityInputSpider` inherits `IdentityCrawler`; it routes `InputDocument`
  and `InputQuery` values through the same pipeline without fetching.

`DocumentTitlePipeline` demonstrates moving extraction out of a spider: it
reads the document item emitted by `UrlCrawler` and adds its HTML title. The
following `UrlAuditPipeline` logs `initial_url` plus every URL the spider
scheduled or received. Finally, `LongscrapePipeline` converts items to core
records at its sink boundary and persists them through `MongoRecordPipeline`.

The crawler and pipeline behavior lives in `with_scrapy/spiders/` and
`with_scrapy/pipelines.py`; `main.py` is only the queue/service bootstrap.
