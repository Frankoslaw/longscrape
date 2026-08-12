# longscrape

> [!WARNING]
> The canonical repository and place to report issues is
> [forgejo.frankoslaw.top/frankoslaw/longscrape](https://forgejo.frankoslaw.top/frankoslaw/longscrape).

`longscrape` is a small set of direct scraping adapters. The application owns
its execution loop; there are no built-in workers, crawlers, rate limiters, or
follow-up-job orchestration.

```text
Job → Fetcher (when needed) → Document → Extractor → Transformer(s) → RecordStore
```

Use `longscrape-core` for `Job`, explicit inputs, documents, records, queues,
and in-memory stores. Use `longscrape` for HTTPX, Playwright, stealth,
Patchright, browser capture, and MongoDB adapters. Use `longscrape-scrapy` for
Scrapy spiders and the Scrapy item-to-record pipeline.

## Install

```bash
uv sync
uv sync --extra playwright
uv sync --extra patchright
uv sync --extra stealth
uv sync --extra fastapi
uv sync --extra mongodb
```

## Direct HTTP example

```python
from longscrape import HttpxFetcher
from longscrape_core import InputUrl, Job

async with HttpxFetcher() as fetcher:
    document = await fetcher.fetch(
        Job(kind="company", input=InputUrl("https://example.com"))
    )
```

The caller can pass the returned document to any extractor, apply its own
transformers, and save records to a core or MongoDB store.

## Examples

- [Browser quotes scraper](examples/quotes.py): explicit queue draining with
  Patchright.
- [MongoDB fetch](examples/mongodb/simple.py) and
  [document re-extraction](examples/mongodb/reextract.py).
- [Browser extension capture](examples/browser_plugin): FastAPI capture app
  creating `Job(InputDocument(...))` values.
- [Scrapy integration](examples/with_scrapy): queued initial jobs processed by
  `longscrape-scrapy`.
