# longscrape

`longscrape` is an asynchronous scraping toolkit built around a small pipeline:

```text
Task → Fetcher → RawEntry → Extractor → RichEntry + child Tasks
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

Each task has a deterministic `task.hash`, calculated from `kind` and `query`.
Raw-entry storage uses that hash as its lookup key. Use `task.spawn(...)` from
an extractor to create a child task while changing only the required fields.

### `Fetcher` and `RawEntry`

A fetcher implements `FetcherPort`. It receives a task, performs the network or
browser work, and returns the unprocessed source as a `RawEntry`.

```python
class HttpFetcher:
    def __init__(self, http: HttpxManager) -> None:
        self._http = http

    def get_base_domain(self) -> str:
        return "example.com"

    async def fetch(self, task: Task) -> RawEntry:
        response = await self._http.get(task.query)
        return RawEntry(
            task_hash=task.hash,
            url=str(response.url),
            content=response.text,
            content_type=response.headers.get("content-type", "text/html"),
            status_code=response.status_code,
        )
```

`RawEntry` is the fetched document before parsing. It retains the final URL,
body, content type, status code, and fetch time. Caching raw entries is useful
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
    HttpFetcher(),
    CountryExtractor(),
    task_kind="country-page",
    raw_entry_store=InMemoryRawEntryStore(),
)
result = await worker.run(Task(kind="country-page", query="https://example.com"))
```

### Raw-entry stores

`InMemoryRawEntryStore` is the simplest option. It is process-local and is
ideal for one program run, tests, and the browser example.

`PyMongoRawEntryStore` persists raw entries in MongoDB. It has no automatic
expiration: an entry remains until it is explicitly replaced or removed. The
store is keyed by `task.hash`, so use stable, JSON-serializable task queries.

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

It enqueues child tasks, routes them by `task.kind`, and stops once all work is
complete. `await crawler.run(seed)` is the collecting alternative and returns a
list of entries.

Resources are never discovered from workers. Passing `resources=[http]` makes
the context manager call their `start()` and `stop()` methods; use
`manage_resources=False` when the caller owns a shared browser or client.
`InMemoryTaskQueue` remains available when a custom queue is needed.
