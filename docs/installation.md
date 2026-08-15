# Installation

longscrape is currently distributed from this Git repository as three Python
packages. Until releases are published to PyPI, install the packages you use
with `uv` and Git URLs. The packages require Python 3.14 or newer.

The repository URL used below is:

```text
git+ssh://git@ssh.frankoslaw.top:2222/frankoslaw/longscrape.git
```

For reproducible deployments, replace the branch-less URL with a reviewed tag
or commit, for example `.../longscrape.git@<commit>#subdirectory=...`.

## Choose packages

| Package | Install when you need | Includes |
| --- | --- | --- |
| `longscrape-core` | Shared application models and interfaces. | Jobs, inputs, documents, records, queues, stores, fetcher/extractor/transformer protocols, and in-memory implementations. |
| `longscrape` | Direct, application-owned scraping. | HTTPX fetcher plus optional browser fetchers, FastAPI capture receiver, and MongoDB stores. |
| `longscrape-scrapy` | In-process Scrapy crawls driven by core jobs. | `JobSpider`, `CrawlService`, wrapper request/response/item types, crawlers, and the record pipeline. |

`longscrape` and `longscrape-scrapy` both depend on `longscrape-core`. Add
the core package explicitly while installing from Git so `uv` resolves the
workspace dependency from this repository rather than looking for a PyPI
release.

## Core only

```bash
uv add 'longscrape-core @ git+ssh://git@ssh.frankoslaw.top:2222/frankoslaw/longscrape.git#subdirectory=packages/longscrape_core'
```

Use this for applications that provide their own fetchers, extractors,
transformers, queues, and stores.

## Direct adapters

```bash
uv add \
  'longscrape-core @ git+ssh://git@ssh.frankoslaw.top:2222/frankoslaw/longscrape.git#subdirectory=packages/longscrape_core' \
  'longscrape @ git+ssh://git@ssh.frankoslaw.top:2222/frankoslaw/longscrape.git#subdirectory=packages/longscrape'
```

This installs the HTTPX-based `HttpxFetcher`. Add an optional feature by
including its extra in the package name:

```bash
# Browser automation
uv add 'longscrape[playwright] @ git+ssh://git@ssh.frankoslaw.top:2222/frankoslaw/longscrape.git#subdirectory=packages/longscrape'
uv add 'longscrape[stealth] @ git+ssh://git@ssh.frankoslaw.top:2222/frankoslaw/longscrape.git#subdirectory=packages/longscrape'
uv add 'longscrape[patchright] @ git+ssh://git@ssh.frankoslaw.top:2222/frankoslaw/longscrape.git#subdirectory=packages/longscrape'

# Browser-capture API or MongoDB-backed stores
uv add 'longscrape[fastapi] @ git+ssh://git@ssh.frankoslaw.top:2222/frankoslaw/longscrape.git#subdirectory=packages/longscrape'
uv add 'longscrape[mongodb] @ git+ssh://git@ssh.frankoslaw.top:2222/frankoslaw/longscrape.git#subdirectory=packages/longscrape'
```

The optional features are:

| Extra | Enables |
| --- | --- |
| `playwright` | `PlaywrightFetcher` and `PlaywrightManager`. |
| `stealth` | `StealthFetcher` and `StealthPlaywrightManager`. |
| `patchright` | `PatchrightFetcher` and `PatchrightManager`. |
| `fastapi` | `longscrape.capture.create_capture_app()` for receiving browser captures. |
| `mongodb` | `PyMongoDocumentStore` and `PyMongoRecordStore`. |
| `all` | Every optional feature above. |

Browser runtimes also require the appropriate browser installation step for
the selected driver; installing the Python extra alone does not install a
browser executable.

## Scrapy integration

```bash
uv add \
  'longscrape-core @ git+ssh://git@ssh.frankoslaw.top:2222/frankoslaw/longscrape.git#subdirectory=packages/longscrape_core' \
  'longscrape-scrapy @ git+ssh://git@ssh.frankoslaw.top:2222/frankoslaw/longscrape.git#subdirectory=packages/longscrape_scrapy'
```

Configure a Scrapy project with a `JobSpider` subclass whose `name` matches
the queued job's `kind`. To persist pipeline output, add `LongscrapePipeline`
to `ITEM_PIPELINES` and set either `LONGSCRAPE_RECORD_STORE` or
`LONGSCRAPE_RECORD_SINK`. Native Scrapy items must provide a non-empty
`source_url`; `UrlCrawler` itself emits a `LongscrapeDocumentItem`, which the
pipeline can convert to a core `Record`.

See [Concepts and architecture](concepts.md) for the component model.

## TODO: PyPI releases

When the packages are published to PyPI, replace the Git URL instructions
with versioned installs such as `uv add longscrape-core`, `uv add longscrape`,
and `uv add longscrape-scrapy`. Before doing so, document the supported
release/version policy and publish matching releases of the dependent
packages.
