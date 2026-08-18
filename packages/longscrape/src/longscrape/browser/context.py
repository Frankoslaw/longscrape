from typing import Any

from longscrape_core import ContextKey

CURRENT_PAGE = ContextKey[Any]("longscrape.browser.current_page")
