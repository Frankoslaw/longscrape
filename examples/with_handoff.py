"""Manually hand off a blocked fetch to a headed browser.

Run from the repository root:

    uv run --with playwright playwright install chromium
    uv run --with playwright python examples/with_handoff.py

If the initial headless request shows ``Login``, ``ManualHandoff`` opens a
headed browser with the same session. Log in and press Enter (or wait two
minutes); ``HandoffFetcher`` then retries with the updated session.
"""

import asyncio

from longscrape import Document, FetchFailure, FetchFailureKind, InputUrl, Job
from longscrape.browser import BrowserConfig, BrowserManager, ManualHandoff
from longscrape.browser.provider import PlaywrightBrowserProvider
from longscrape.fetchers import BrowserFetcher, HandoffFetcher
from parsel import Selector

URL = "https://quotes.toscrape.com/"
LOGIN_STATUS = (
    "div.row:nth-child(1) > div:nth-child(2) > p:nth-child(1) > a:nth-child(1)"
)


def login_detector(document: Document, job: Job) -> FetchFailure | None:
    status = (
        Selector(text=document.content.decode(errors="replace"))
        .css(f"{LOGIN_STATUS}::text")
        .get("")
        .strip()
        .lower()
    )
    if "logout" in status:
        return None
    return FetchFailure(
        FetchFailureKind.BLOCKED,
        f"Login-status link did not contain Logout: {status!r}",
        url=document.url,
    )


async def main() -> None:
    config = BrowserConfig(launch_options={"headless": True})
    browser = BrowserManager(PlaywrightBrowserProvider(config), config)
    await browser.start()
    try:
        fetcher = HandoffFetcher(
            BrowserFetcher(browser),
            detector=login_detector,
            handoff=ManualHandoff(browser),
        )
        job = Job("quotes", InputUrl(URL))
        documents = [document async for document in fetcher.fetch(job)]
        print(f"Session handoff succeeded; fetched {documents[0].url}")
    finally:
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())
