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
    )
