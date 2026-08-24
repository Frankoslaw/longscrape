"""Structlog event sink; imported only when configured."""

from typing import Any

from longscrape.observability.base import Event


class StructlogSink:
    def __init__(self, logger: Any | None = None) -> None:
        try:
            import structlog as structlog_module
        except ImportError as error:  # pragma: no cover
            raise ImportError(
                "Structlog observation requires 'longscrape[structlog]'"
            ) from error
        self._logger = logger or structlog_module.get_logger("longscrape.pipeline")

    def emit(self, event: Event) -> None:
        self._logger.info(
            event.kind,
            scope=event.name,
            scope_id=event.scope_id,
            parent_scope_id=event.parent_scope_id,
            duration_ms=event.duration_ms,
            **event.attributes,
        )
