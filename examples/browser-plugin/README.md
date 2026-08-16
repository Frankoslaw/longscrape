# Browser-plugin raw-input example

This Firefox extension captures rendered pages and sends their HTML to a local
Longscrape receiver. The example configures LinkedIn people-search and profile
routes, but the extension itself is generic: route matching and task-kind
selection live in its settings.

> [!WARNING]
> This is an educational example, not a production scraper. LinkedIn is a
> protected site, and automated collection may violate its Terms of Service.
> Use it only with explicit authorisation and at your own risk.

Run the receiver:

```bash
uv run uvicorn --app-dir examples/browser-plugin linkedin:app --host 127.0.0.1 --port 8000
```

Each extracted record is printed by the receiver and the extension logs the
number of records in the browser console. The receiver uses
`BrowserCaptureServer`, which creates an `InputDocument` job and runs the
capture handler supplied by the application. The LinkedIn example matches on
the capture's `kind` and runs the corresponding extractor directly; no
fetcher, cache, or rate limiter is used.

Set `MONGODB_URI` before starting the receiver to persist people and profile
records to the `linkedin_people` and `linkedin_profiles` collections. Without
it, the example uses process-local in-memory record stores.

The receiver URL is `http://127.0.0.1:8000/v1/captures`. Keep the Uvicorn
process running while the extension is loaded; Firefox reports
`NS_ERROR_CONNECTION_REFUSED` when nothing is listening on that address.

In Firefox, open `about:debugging#/runtime/this-firefox`, choose **Load
Temporary Add-on**, and select `extension/manifest.json`. Its settings page can
change the receiver URL and routes. A route is a JSON object with a `match` URL
glob and a `kind`, plus an optional static `context` object. For example:

```json
[
  {
    "match": "https://example.com/products/*",
    "kind": "product-page",
    "context": {"locale": "en"}
  }
]
```

`*` matches any sequence of URL characters. Every capture also adds the current
`url` and `page_title` to the context. The extension has access to all URLs so its
route list can be changed without rebuilding it; keep that list narrow and use
this only for pages and data you are authorised to process.
