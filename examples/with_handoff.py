"""Manually hand off a Quotes to Scrape session to a headed browser.

Run from the repository root:

    uv run --with playwright playwright install chromium
    uv run --with playwright python examples/with_handoff.py

The first browser is headless. If its page's login-status link says ``Login``,
the example opens a second, headed browser. Log in there, return to the
terminal, and press Enter. The updated Playwright storage state is then used to
create a replacement context in the original headless browser.
"""

import asyncio

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

URL = "https://quotes.toscrape.com/"
LOGIN_STATUS = (
    "div.row:nth-child(1) > div:nth-child(2) > p:nth-child(1) > a:nth-child(1)"
)


async def is_logged_in(page: Page) -> bool:
    await page.goto(URL)
    text = await page.locator(LOGIN_STATUS).inner_text()
    status = text.strip().lower()
    if "logout" in status:
        return True
    if "login" in status:
        return False
    raise RuntimeError(f"Login-status link did not contain Login or Logout: {text!r}")


async def handoff(
    fetch_browser: Browser, fetch_context: BrowserContext
) -> BrowserContext:
    """Return a fresh fetch context populated with the manual session state."""
    original_state = await fetch_context.storage_state()
    manual_browser = await fetch_browser.browser_type.launch(headless=False)
    manual_context = await manual_browser.new_context(storage_state=original_state)
    manual_page = await manual_context.new_page()
    try:
        await manual_page.goto(URL)
        prompt = "Log in in the headed browser, then press Enter: "
        await asyncio.to_thread(input, prompt)
        updated_state = await manual_context.storage_state()
    finally:
        await manual_context.close()
        await manual_browser.close()

    await fetch_context.close()
    return await fetch_browser.new_context(storage_state=updated_state)


async def main() -> None:
    async with async_playwright() as playwright:
        fetch_browser = await playwright.chromium.launch(headless=True)
        fetch_context = await fetch_browser.new_context()
        try:
            page = await fetch_context.new_page()
            logged_in = await is_logged_in(page)
            print(f"Initial login status: {'logout' if logged_in else 'login'}")

            if not logged_in:
                await page.close()
                fetch_context = await handoff(fetch_browser, fetch_context)
                page = await fetch_context.new_page()
                logged_in = await is_logged_in(page)

            if not logged_in:
                raise RuntimeError("The headed-browser session was not logged in")
            print("Session handoff succeeded; headless scraping can resume.")
        finally:
            await fetch_context.close()
            await fetch_browser.close()


if __name__ == "__main__":
    asyncio.run(main())
