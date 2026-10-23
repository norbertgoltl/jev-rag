from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from jev_rag_api.api.router import router
from jev_rag_api.application.ports.readiness import ReadinessProbe, UnconfiguredReadinessProbe

from jev_rag_api.core.config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(settings: Settings | None = None, readiness_probe: ReadinessProbe | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()
    application = FastAPI(title="Jev RAG Foundation API", version="0.1.0", lifespan=lifespan)
    application.state.settings = config
    application.state.readiness_probe = readiness_probe if readiness_probe is not None else UnconfiguredReadinessProbe()
    application.add_middleware(
        CORSMiddleware, allow_origins=config.cors_allowed_origins,
        allow_methods=["GET", "OPTIONS"], allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"], allow_credentials=False,
    )
    application.include_router(router)
    return application


app = create_app()
