from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BrowserConfig:
    browser_type: str = "chromium"
    launch_options: dict[str, Any] = field(default_factory=dict)
    context_options: dict[str, Any] = field(default_factory=dict)
