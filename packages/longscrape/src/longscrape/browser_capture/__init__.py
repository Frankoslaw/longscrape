from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from longscrape.browser_capture.server import BrowserCapture, BrowserCaptureServer

__all__ = ["BrowserCapture", "BrowserCaptureServer"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)
    return getattr(import_module("longscrape.capture.server"), name)
