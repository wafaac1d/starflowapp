import logging
from typing import cast

import structlog
from structlog.typing import EventDict, WrappedLogger

from starflow.i18n.guard import redact


def redact_processor(
    _logger: WrappedLogger,
    _method: str,
    event_dict: EventDict,
) -> EventDict:
    cleaned = redact(dict(event_dict))
    if not isinstance(cleaned, dict):
        return event_dict
    event_dict.clear()
    for key, value in cleaned.items():
        event_dict[str(key)] = value
    return event_dict


def configure_logging(level: str) -> None:
    numeric = logging.getLevelNamesMapping()[level]
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
