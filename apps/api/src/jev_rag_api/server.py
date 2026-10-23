import uvicorn
from pydantic import ValidationError

from jev_rag_api.core.config import Settings


def main() -> None:
    try:
        settings = Settings()
    except ValidationError:
        raise SystemExit("Invalid server configuration. Check the documented settings.") from None
    uvicorn.run(
        "jev_rag_api.main:app", host=settings.api_host, port=settings.api_port,
        reload=settings.app_env == "development", access_log=False,
        log_level=settings.log_level.lower(),
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": "jev_rag_api.core.logging.JsonFormatter"}},
            "handlers": {"console": {
                "class": "logging.StreamHandler", "formatter": "json",
                "stream": "ext://sys.stderr",
            }},
            "loggers": {
                "uvicorn": {"handlers": ["console"], "propagate": False},
                "uvicorn.error": {"handlers": ["console"], "propagate": False},
                "uvicorn.access": {"handlers": [], "propagate": False},
            },
        },
    )
