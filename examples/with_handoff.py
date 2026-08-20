"""Manually recover a JS-rendered login page before extracting its content.

Run from the repository root:

    uv run --with playwright playwright install chromium
    uv run --with playwright python -m examples.with_handoff

The first headless request loads the delayed page and verifies that the account
link says ``Logout``. If it says ``Login``, the recovery policy asks
``ManualHandoff`` to open the same session in a headed browser. Log in there,
press Enter, and the fetcher retries with the copied session state.
"""

import asyncio

from longscrape import (
    Document,
    InputUrl,
    Job,
)
from longscrape.browser import BrowserConfig, BrowserManager, ManualHandoff
from longscrape.browser.provider import PlaywrightBrowserProvider
from longscrape.fetchers import BrowserFetcher, FetcherBuilder
from parsel import Selector

URL = "https://quotes.toscrape.com/"
LOGIN_STATUS = ".col-md-4 > p:nth-child(1) > a:nth-child(1)"


class LoginRequiredError(Exception):
    pass


def login_detector(document: Document, job: Job) -> Exception | None:
    status = (
        Selector(text=document.content.decode(errors="replace"))
        .css(f"{LOGIN_STATUS}::text")
        .get("")
        .strip()
        .lower()
    )
    if status == "logout":
        return None
    return LoginRequiredError(f"Account link showed {status!r}, not 'Logout'")


async def wait_for_quotes(page: object) -> None:
    await page.wait_for_selector(".quote")  # type: ignore[attr-defined]


async def main() -> None:
    scrape_config = BrowserConfig(launch_options={"headless": True})
    handoff_config = BrowserConfig(launch_options={"headless": False})
    browser = BrowserManager(PlaywrightBrowserProvider(scrape_config), scrape_config)
    handoff_browser = BrowserManager(
        PlaywrightBrowserProvider(handoff_config), handoff_config
    )
    await browser.start()
    await handoff_browser.start()
    try:
        fetcher = (
            FetcherBuilder()
            .base(BrowserFetcher(browser, page_ready=wait_for_quotes))
            .handoff(
                detector=login_detector,
                handoff_strategy=ManualHandoff(browser, handoff_browser),
            )
            .retry(max_retries=3)
            .build()
        )
        documents = [
            document async for document in fetcher.fetch(Job("quotes", InputUrl(URL)))
        ]
        print(f"Logged-in session fetched {documents[0].url}")
    finally:
        await handoff_browser.stop()
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())
