# longscrape

> [!WARNING]
> The canonical repository and place to report issues is
> [forgejo.frankoslaw.top/frankoslaw/longscrape](https://forgejo.frankoslaw.top/frankoslaw/longscrape).
> [Frankoslaw/longscrape](https://github.com/Frankoslaw/longscrape) is a read-only GitHub mirror.

> [!CAUTION]
> This library is in alpha and its API may change.

`longscrape` is an asynchronous scraping toolkit built from small, composable
pipeline stages:

```text
Job → Fetcher → Document → Extractor → Record → Transformer
                    └──────────────→ JobRequest (follow-up work)
```

The stable domain types and pipeline contracts live in `longscrape-core`.
`longscrape` provides practical adapters such as HTTP and browser fetchers,
cache and rate-limit decorators, document stores, and a browser-capture server.

## Install

```bash
uv sync
```

Optional adapters:

```bash
uv sync --extra playwright  # browser fetcher
uv sync --extra patchright  # Patchright browser support
uv sync --extra mongodb     # MongoDB document store
```

## A pipeline

Create a `Job`, pass it to a fetcher, and pass the document stream to an
extractor. Each stage is an async iterable, so records are handled as soon as
they are available.

```python
import httpx

from longscrape import InputUrl, Job
from longscrape.adapters import HttpxFetcher

job = Job("article", InputUrl("https://example.com/article"))
async with httpx.AsyncClient() as http:
    documents = HttpxFetcher(http).fetch(job)
    async for record in ArticleExtractor().extract(documents, job):
        print(record.data)
```

An extractor receives `documents`, `job`, and an optional `JobSubmitter`.
Yield `Record` values and use `await submitter.submit(JobRequest(...))` for
discovered work. The quotes example shows a minimal in-memory queue submitter.

Decorators compose around any fetcher:

```python
fetcher = RateLimitedFetcher(
    CachedFetcher(HttpxFetcher(http), InMemoryDocumentStore()),
    LeakyBucketRateLimiter(requests_per_second=1),
)
```

`CachedFetcher` uses an `InputUrl` as its default key. Use its `read`, `write`,
and `max_age` options to control cache behaviour.

## Examples

### Quotes crawler

[examples/quotes.py](examples/quotes.py) follows quote and author pages with a
`JobRequest` queue. It combines the HTTP fetcher with cache and per-domain rate
limiting. Set `MONGODB_URI` to persist documents; otherwise it uses an
in-memory store. With MongoDB configured, extracted quote and author records
are written to separate `quotes` and `authors` collections through
`PyMongoRecordStore` and `RecordSink`.

```bash
uv run python examples/quotes.py
```

### Re-extract cached quotes

[examples/reextract.py](examples/reextract.py) runs the quote and author
extractors over cached MongoDB documents, without making HTTP requests. It is a
no-op with the default in-memory store because that store does not survive a
separate process.

```bash
docker compose -f compose.dev.yml up -d
MONGODB_URI=mongodb://localhost:27017 uv run --extra mongodb python examples/quotes.py
MONGODB_URI=mongodb://localhost:27017 uv run --extra mongodb python examples/reextract.py
```

### Browser captures

[examples/browser-plugin](examples/browser-plugin) contains a temporary Firefox
extension and a local receiver. `BrowserCaptureServer` turns captured HTML into
an `InputDocument` job and passes it to the registered extractor; no fetcher is
needed. Use it only for pages and data you are authorised to process.

```bash
uv run uvicorn --app-dir examples/browser-plugin linkedin:app --host 127.0.0.1 --port 8765
```
