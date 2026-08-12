# Browser-plugin raw-input example

This Firefox extension captures rendered pages and sends their HTML to a local
Longscrape receiver. The example configures LinkedIn people-search and profile
routes, but the extension itself is generic: route matching and task-kind
selection live in its settings.

Run the receiver:

```bash
uv run uvicorn --app-dir examples/browser-plugin linkedin:app --host 127.0.0.1 --port 8765
```

Each extracted record is printed by the receiver and the extension logs the
number of extracted items in the browser console. The receiver uses a
`CaptureScraper` with one core `Extractor` per capture kind. The capture app
creates a `Job(InputDocument(...))`; `CaptureScraper` routes it by `job.kind`,
stores the document, applies any configured transformers, and saves records.
No fetcher, worker, or crawler is involved.

In Firefox, open `about:debugging#/runtime/this-firefox`, choose **Load
Temporary Add-on**, and select `extension/manifest.json`. Its settings page can
change the receiver URL and routes. A route is a JSON object with a `match` URL
glob and a `kind`, plus an optional static `query` object. For example:

```json
[
  {
    "match": "https://example.com/products/*",
    "kind": "product-page",
    "query": {"locale": "en"}
  }
]
```

`*` matches any sequence of URL characters. Every capture also adds the current
`url` and `page_title` to the query. The extension has access to all URLs so its
route list can be changed without rebuilding it; keep that list narrow and use
this only for pages and data you are authorised to process.
