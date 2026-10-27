import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from jev_rag_api.api.schemas.health import (
    DownDependencies,
    LivenessResponse,
    NotReadyResponse,
    ReadinessResponse,
    UpDependencies,
)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get(
    "/ready", response_model=ReadinessResponse, responses={503: {"model": NotReadyResponse}}
)
async def readiness(request: Request) -> ReadinessResponse | JSONResponse:
    try:
        async with asyncio.timeout(request.app.state.settings.qdrant_timeout_seconds):
            up = await request.app.state.readiness_probe.check_health()
    except TimeoutError, OSError:
        logging.getLogger(__name__).warning("Qdrant readiness deadline exceeded")
        up = False
    if up:
        return ReadinessResponse(dependencies=UpDependencies())
    body = NotReadyResponse(dependencies=DownDependencies())
    return JSONResponse(body.model_dump(), status_code=503)
