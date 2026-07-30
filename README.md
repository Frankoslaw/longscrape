# longscrape

> [!WARNING]
> The canonical repository and place to report issues is
> [forgejo.frankoslaw.top/frankoslaw/longscrape](https://forgejo.frankoslaw.top/frankoslaw/longscrape).
> [Frankoslaw/longscrape](https://github.com/Frankoslaw/longscrape) is a read-only GitHub mirror.

> [!CAUTION]
> This library is in the alpha stage. Regular API-breaking changes are to be expected.

`longscrape` is an asynchronous scraping toolkit built around a small pipeline:

```text
FetchRequest → Fetcher → RawEntry → Extractor → RichEntry + child inputs
RawInput ───────────────────→ Extractor
```

You provide the site-specific fetching and extraction logic. The library runs
the pipeline, optionally rate-limits network requests, and can reuse saved raw
responses before any network request is made.

## Install

The core package includes the HTTP client and HTML selector dependencies:

```bash
uv sync
```

Browser and MongoDB adapters are optional:

```bash
uv sync --extra playwright  # Playwright browser adapter
uv sync --extra patchright  # Patchright browser adapter
uv sync --extra stealth     # Playwright with playwright-stealth
uv sync --extra mongodb     # PyMongo raw-entry storage
```

`patchright` and `stealth` include Playwright automatically. Importing the core
package does not import any of these optional adapters.

## Core concepts

### `Task`

A `Task` describes one unit of work. Its `kind` selects the appropriate worker,
and its `query` contains the fetcher input—usually a URL.

```python
task = Task(kind="country-page", query="https://example.com/countries")
```

`Task` remains an alias for `FetchRequest`. Its `query` can be any
JSON-serializable shape, such as a URL string or `{"city": "Warsaw",
"country": "PL"}`. A deterministic request fingerprint is calculated from
`kind` and `query`; callers do not supply cache keys. Put every
request-affecting setting in the query so it contributes to the fingerprint.

### `Fetcher` and `RawEntry`

A fetcher implements `FetcherPort`. It receives a task, performs the network or
browser work, and returns the unprocessed source as a `RawEntry`.

```python
fetcher = HttpxFetcher(http, base_domain="example.com")
```

`RawEntry` is the fetched document before parsing. Its body is `str | bytes`;
it retains the final URL, content type, status code, and fetch time. Caching raw entries is useful
because extraction can be changed and rerun without fetching the page again.

For browser scraping, use the optional `DefaultFetcher` together with a
`PlaywrightManager` or `PatchrightManager` instead of writing this fetcher.

### `Extractor`, `RichEntry`, and `ExtractionResult`

An extractor implements `ExtractorPort`. It turns a `RawEntry` into structured
`RichEntry` values and may schedule further tasks. `DefaultExtractor` supplies
an `allowed_domain` compatibility check.

```python
class CountryExtractor(DefaultExtractor[str]):
    def __init__(self) -> None:
        super().__init__(allowed_domain="example.com")

    async def extract(
        self, task: Task, raw_entry: RawEntry
    ) -> ExtractionResult[str]:
        selector = Selector(text=raw_entry.content)
        countries = [
            RichEntry(url=raw_entry.url, data=name.strip())
            for name in selector.css(".country-name::text").getall()
        ]
        return ExtractionResult(items=countries, tasks=[])
```

Unlike `RawEntry`, a `RichEntry` is application data: `data` can be any typed
value, such as a dictionary, dataclass, or string. `ExtractionResult.items`
contains the extracted records; `ExtractionResult.tasks` contains discovered
follow-up work.

### `RawInput` and `ScraperWorker`

`RawInput` sends an already acquired entry straight to an extractor. It has the
same `kind` and flexible `query` fields as `FetchRequest`, so an extractor gets
the same context from browser-plugin and fetched inputs.

```python
input = RawInput(
    kind="company-page",
    query={"company_id": "acme-123"},
    raw_entry=RawEntry(url=plugin_page.url, content=plugin_page.html),
)
worker = ScraperWorker(None, CompanyExtractor(), task_kind="company-page")
async with Crawler({"company-page": worker}) as crawler:
    companies = await crawler.run_inputs(input)
```

### `ScraperWorker`

`ScraperWorker` composes one fetcher and one extractor. It optionally limits
requests and reads/writes a raw-entry store. Its execution order is:

```text
check task kind → look up raw entry → (on miss) rate-limit → fetch → store → extract
```

A cache hit bypasses both the fetcher and the rate limiter. Use `task_kind` when
a worker should only accept a particular kind of task.

```python
worker = ScraperWorker(
    HttpxFetcher(http, base_domain="example.com"),
    CountryExtractor(),
    task_kind="country-page",
    raw_entry_store=InMemoryRawEntryStore(),
)
result = await worker.run(Task(kind="country-page", query="https://example.com"))
```

`cache_policy` controls raw-entry reuse for `FetchRequest`s: `CachePolicy.use()` is the default,
`CachePolicy.refresh()` replaces an existing entry, `CachePolicy.bypass()` does
not read or write the store, and `CachePolicy.ttl(hours=24)` refetches stale
entries. `rate_limit_key` optionally separates rate-limit grouping from the
fetcher's base domain.

### Raw-entry stores

`InMemoryRawEntryStore` is the simplest option. It is process-local and is
ideal for one program run, tests, and the browser example.

`PyMongoRawEntryStore` persists raw entries in MongoDB. It has no automatic
expiration: an entry remains until it is explicitly replaced or removed. The
store is keyed by the request fingerprint; use JSON-serializable queries when
relying on the default.

## Examples

### Browser quotes crawler

[examples/quotes.py](examples/quotes.py) crawls quotes and author pages using
Patchright, an in-memory raw-entry store, a rate limiter, and an in-memory task
queue.

```bash
uv run --extra patchright python examples/quotes.py
```

### HTTP scraper with MongoDB raw storage

[examples/simple_mongodb.py](examples/simple_mongodb.py) fetches country names
from ScrapethisSite. On the first run it saves the raw HTML to MongoDB; later
runs with the same task use the stored HTML instead.

```bash
docker compose -f compose.dev.yml up -d
uv run --extra mongodb python examples/simple_mongodb.py
```

The included [compose.dev.yml](compose.dev.yml) exposes MongoDB at
`mongodb://localhost:27017`. Set `MONGODB_URI` to use another deployment.

### Browser-plugin raw input

[examples/browser-plugin](examples/browser-plugin) contains a temporary Firefox
extension and a local LinkedIn people-search/profile extractor. The extension
sends rendered HTML to the example receiver, which creates `RawInput` values;
the flow therefore has no fetcher. Use it only for pages and data you are
authorised to process.

## Queues and crawling

`Crawler` runs the queue loop for you. Register one worker for each task kind,
then stream items as they are extracted:

```python
async with Crawler(
    {"country-page": worker},
    resources=[http],
    concurrency=4,
) as crawler:
    async for item in crawler.stream(Task(kind="country-page", query=URL)):
        print(item.data)
```

It enqueues child inputs, routes them by `input.kind`, and stops once all work
is complete. `await crawler.run(seed)` is the collecting alternative. The
equivalent `stream_inputs(...)` and `run_inputs(...)` names make it explicit
that both `FetchRequest` and `RawInput` are accepted.

Resources are never discovered from workers. Passing `resources=[http]` makes
the context manager call their `start()` and `stop()` methods; use
`manage_resources=False` when the caller owns a shared browser or client.
`InMemoryTaskQueue` remains available when a custom queue is needed.
