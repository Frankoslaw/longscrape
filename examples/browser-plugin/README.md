# Browser-plugin raw-input example

This Firefox extension captures rendered LinkedIn people-search and profile
pages and sends their HTML to the local `linkedin.py` receiver. The receiver
creates a `RawInput`, so no Longscrape fetcher, cache, or rate limiter is used.

Run the receiver:

```bash
uv run uvicorn --app-dir examples/browser-plugin linkedin:app --host 127.0.0.1 --port 8765
```

Each extracted `item.data` is printed by the receiver and the extension logs
the number of extracted items in the browser console.

In Firefox, open `about:debugging#/runtime/this-firefox`, choose **Load
Temporary Add-on**, and select `extension/manifest.json`. Its settings page can
change the receiver URL. Use this only for pages and data you are authorised to
process.
