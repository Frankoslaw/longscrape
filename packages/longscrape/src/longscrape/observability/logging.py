"""Standard-library logging integration for observation scopes."""

import logging

from longscrape.observability.base import Event, current_scope


def get_logger(name: str | None = None) -> logging.Logger:
    if name is None or name == "longscrape" or name.startswith("longscrape."):
        return logging.getLogger(name or "longscrape")
    return logging.getLogger(f"longscrape.{name}")


class _ScopeFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        scope = current_scope()
        fields = dict(scope.attributes) if scope else {}
        if scope:
            fields.update(
                scope_id=scope.scope_id,
                parent_scope_id=scope.parent_scope_id or "",
            )
        record.__dict__["longscrape"] = fields
        return True


def configure_logging(
    *,
    level: int = logging.INFO,
    log_format: str = "%(asctime)s %(levelname)s %(name)s %(message)s",
) -> logging.Logger:
    logger = logging.getLogger("longscrape")
    logger.setLevel(level)
    logger.propagate = False
    if not any(
        getattr(handler, "_longscrape_handler", False) for handler in logger.handlers
    ):
        handler = logging.StreamHandler()
        handler._longscrape_handler = True  # type: ignore[attr-defined]
        handler.setFormatter(logging.Formatter(log_format))
        handler.addFilter(_ScopeFilter())
        logger.addHandler(handler)
    return logger


class LoggingSink:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or get_logger("longscrape.pipeline")

    def emit(self, event: Event) -> None:
        fields = {**event.attributes, "scope": event.name, "scope_id": event.scope_id}
        if event.kind == "scope.failed":
            self._logger.error(
                "%s", event.kind, extra={"longscrape": fields}, exc_info=event.error
            )
        else:
            self._logger.info("%s", event.kind, extra={"longscrape": fields})
