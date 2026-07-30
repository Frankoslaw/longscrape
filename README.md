# longscrape

## Optional adapters

Browser and MongoDB integrations are optional dependencies:

```bash
uv sync --extra playwright
uv sync --extra patchright
uv sync --extra stealth
uv sync --extra mongodb
```

`patchright` and `stealth` include Playwright automatically.

## MongoDB example

Start a local MongoDB instance, then run the basic cached scraper:

```bash
docker compose -f compose.dev.yml up -d
uv run --extra mongodb python examples/simple_mongodb.py
```

The example requests `https://www.scrapethissite.com/pages/simple/`, stores its
raw HTML under the task hash, and uses that stored response on subsequent runs.
