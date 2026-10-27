import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

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


def configure_logging(level: str) -> None:
    if not any(getattr(handler, "foundation_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler.foundation_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
