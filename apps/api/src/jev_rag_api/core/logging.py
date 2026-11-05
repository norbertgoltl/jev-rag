import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import cache
from typing import Any

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger("jev_rag_api")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": "jev-rag-api",
            "event": record.msg,
            "request_id": request_id_context.get(),
        }
        for key in (
            "method",
            "path",
            "status_code",
            "duration_ms",
            "exception_type",
            "provider_request_id",
            "model",
            "question_count",
            "question_types",
            "input_tokens",
            "error_code",
        ):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data, ensure_ascii=True)


@cache
def json_handler() -> logging.Handler:
    """The single JSON stderr handler shared by the application logger."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    return handler


def configure_logging(level: str) -> None:
    if json_handler() not in logger.handlers:
        logger.addHandler(json_handler())
    logger.setLevel(level)
    logger.propagate = False


def uvicorn_log_config() -> dict[str, Any]:
    """Uvicorn logging configuration that routes server logs through ``JsonFormatter``."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"json": {"()": f"{__name__}.JsonFormatter"}},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stderr",
            }
        },
        "loggers": {
            "uvicorn": {"handlers": ["console"], "propagate": False},
            "uvicorn.error": {"handlers": ["console"], "propagate": False},
            "uvicorn.access": {"handlers": [], "propagate": False},
        },
    }
