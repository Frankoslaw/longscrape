# Scrapy project with a longscrape extension

This is a normal Scrapy project.  Its original spider continues to use the
standard CLI and project settings:

```bash
uv run scrapy crawl quotes
```

The additional `quotes_longscrape` spider is driven by a durable longscrape
job.  Its explicit `start()` and `parse()` methods register an `HttpxFetcher`
and reusable extractor after checking for that job, then delegate their
adaptation to `LongscrapeSpider`.  Its transformer and existing `RecordSink`
are registered in `settings.py` as ordinary Scrapy item pipelines.  It still
loads this project's item pipelines and middlewares.

With Redis available, run these commands from this directory in separate
terminals:

```bash
uv run --package longscrape --extra dramatiq dramatiq main
uv run --package longscrape --extra dramatiq python main.py
```
