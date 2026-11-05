from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from jev_rag_api.api.dependencies import AppContainer
from jev_rag_api.api.errors import register_error_handlers
from jev_rag_api.api.router import router
from jev_rag_api.application.ports.decision import DecisionPort
from jev_rag_api.application.ports.readiness import ReadinessProbe
from jev_rag_api.core.config import Settings
from jev_rag_api.core.logging import configure_logging
from jev_rag_api.core.middleware import RequestContextMiddleware
from jev_rag_api.integrations.jev.provider import decision_provider
from jev_rag_api.integrations.qdrant.readiness import QdrantReadinessProbe


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container: AppContainer = app.state.container
    config = container.settings
    async with AsyncExitStack() as stack:
        container.decision_port = await stack.enter_async_context(
            decision_provider(config, container.decision_override)
        )
        owns_probe = container.readiness_probe is None
        if owns_probe:
            client = await stack.enter_async_context(
                httpx.AsyncClient(
                    base_url=str(config.qdrant_url).rstrip("/") + "/",
                    timeout=config.qdrant_timeout_seconds,
                    trust_env=False,
                    follow_redirects=False,
                )
            )
            container.readiness_probe = QdrantReadinessProbe(client)
        try:
            yield
        finally:
            container.decision_port = None
            if owns_probe:
                container.readiness_probe = None


class FoundationAPI(FastAPI):
    def build_middleware_stack(self) -> ASGIApp:
        # CORS and correlation must also wrap Starlette's server-error handler.
        return RequestContextMiddleware(
            CORSMiddleware(
                super().build_middleware_stack(),
                allow_origins=self.state.container.settings.cors_allowed_origins,
                allow_methods=["GET", "OPTIONS"],
                allow_headers=["Content-Type", "X-Request-ID"],
                expose_headers=["X-Request-ID"],
                allow_credentials=False,
            )
        )


def create_app(
    settings: Settings | None = None,
    readiness_probe: ReadinessProbe | None = None,
    decision_port: DecisionPort | None = None,
) -> FastAPI:
    config = settings if settings is not None else Settings()
    configure_logging(config.log_level)
    # Never expose Starlette's debug traceback through the public HTTP API.
    application = FoundationAPI(title="Jev RAG Foundation API", version="0.1.0", lifespan=lifespan)
    application.state.container = AppContainer(
        settings=config, readiness_probe=readiness_probe, decision_override=decision_port
    )
    register_error_handlers(application)
    application.include_router(router)
    return application


app = create_app()
