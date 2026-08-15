import logging
from typing import Final

LOGGER_NAME: Final = "longscrape"
DEFAULT_LOG_LEVEL: Final = logging.INFO
DEFAULT_LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_HANDLER_MARKER: Final = "_longscrape_default_handler"


def get_logger(name: str) -> logging.Logger:
    if name == LOGGER_NAME or name.startswith(f"{LOGGER_NAME}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def configure_logging(
    level: int | str = DEFAULT_LOG_LEVEL,
    *,
    log_format: str = DEFAULT_LOG_FORMAT,
) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(log_format)
    handler = next(
        (
            existing
            for existing in logger.handlers
            if getattr(existing, _HANDLER_MARKER, False)
        ),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler()
        setattr(handler, _HANDLER_MARKER, True)
        logger.addHandler(handler)
    handler.setFormatter(formatter)
    handler.setLevel(level)
    return logger
