from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from jev_rag_api.api.router import router
from jev_rag_api.application.ports.readiness import ReadinessProbe
from jev_rag_api.integrations.qdrant.readiness import QdrantReadinessProbe
from jev_rag_api.core.config import Settings
from jev_rag_api.core.errors import register_error_handlers
from jev_rag_api.core.logging import configure_logging
from jev_rag_api.core.middleware import RequestContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if app.state.readiness_probe is not None:
        yield
        return
    config = app.state.settings
    async with httpx.AsyncClient(
        base_url=str(config.qdrant_url).rstrip("/") + "/",
        timeout=config.qdrant_timeout_seconds, trust_env=False, follow_redirects=False,
    ) as client:
        app.state.readiness_probe = QdrantReadinessProbe(client)
        try:
            yield
        finally:
            app.state.readiness_probe = None


class FoundationAPI(FastAPI):
    def build_middleware_stack(self) -> ASGIApp:
        # CORS and correlation must also wrap Starlette's server-error handler.
        return RequestContextMiddleware(CORSMiddleware(
            super().build_middleware_stack(),
            allow_origins=self.state.settings.cors_allowed_origins,
            allow_methods=["GET", "OPTIONS"],
            allow_headers=["Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
            allow_credentials=False,
        ))


def create_app(
    settings: Settings | None = None, readiness_probe: ReadinessProbe | None = None,
) -> FastAPI:
    config = settings if settings is not None else Settings()
    configure_logging(config.log_level)
    # Never expose Starlette's debug traceback through the public HTTP API.
    application = FoundationAPI(title="Jev RAG Foundation API", version="0.1.0", lifespan=lifespan)
    application.state.settings = config
    application.state.readiness_probe = readiness_probe
    register_error_handlers(application)
    application.include_router(router)
    return application


app = create_app()
