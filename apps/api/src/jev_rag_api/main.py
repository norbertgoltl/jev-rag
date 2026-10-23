from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from jev_rag_api.api.router import router
from jev_rag_api.application.ports.readiness import ReadinessProbe, UnconfiguredReadinessProbe


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(readiness_probe: ReadinessProbe | None = None) -> FastAPI:
    application = FastAPI(title="Jev RAG Foundation API", version="0.1.0", lifespan=lifespan)
    application.state.readiness_probe = readiness_probe if readiness_probe is not None else UnconfiguredReadinessProbe()
    application.add_middleware(
        CORSMiddleware, allow_origins=["http://127.0.0.1:3000"],
        allow_methods=["GET", "OPTIONS"], allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"], allow_credentials=False,
    )
    application.include_router(router)
    return application


app = create_app()
