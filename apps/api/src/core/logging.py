import logging
import sys
from typing import Any

import structlog
from pythonjsonlogger import jsonlogger

from .config import get_settings


def setup_logging() -> None:
    settings = get_settings()

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.format_exc_info,
    ]

    if settings.LOG_FORMAT == "json":
        formatter: logging.Formatter = jsonlogger.JsonFormatter(
            "%(timestamp)s %(level)s %(logger)s %(message)s",
            rename_fields={"level": "severity", "logger": "name"},
        )
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter_processor = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler.setFormatter(formatter_processor)

    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.error").handlers = [handler]
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    # structlog.get_logger()'s return type is loosely typed (Any); the actual
    # runtime type is BoundLogger because setup_logging() configures
    # wrapper_class=structlog.stdlib.BoundLogger above.
    return structlog.get_logger(name)  # type: ignore[no-any-return]
