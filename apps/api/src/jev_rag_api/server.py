import uvicorn
from pydantic import ValidationError

from jev_rag_api.core.config import Settings
from jev_rag_api.core.logging import uvicorn_log_config


def main() -> None:
    try:
        settings = Settings()
    except ValidationError:
        raise SystemExit("Invalid server configuration. Check the documented settings.") from None
    uvicorn.run(
        "jev_rag_api.main:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env == "development",
        access_log=False,
        log_level=settings.log_level.lower(),
        log_config=uvicorn_log_config(),
    )
