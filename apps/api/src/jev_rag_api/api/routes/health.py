import asyncio
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from jev_rag_api.api.dependencies import get_readiness_probe, get_settings
from jev_rag_api.api.schemas.health import (
    DownDependencies,
    LivenessResponse,
    NotReadyResponse,
    ReadinessResponse,
    UpDependencies,
)
from jev_rag_api.application.ports.readiness import ReadinessProbe
from jev_rag_api.core.config import Settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get(
    "/ready", response_model=ReadinessResponse, responses={503: {"model": NotReadyResponse}}
)
async def readiness(
    settings: Settings = Depends(get_settings),
    probe: ReadinessProbe = Depends(get_readiness_probe),
) -> ReadinessResponse | JSONResponse:
    try:
        async with asyncio.timeout(settings.qdrant_timeout_seconds):
            up = await probe.check_health()
    except TimeoutError, OSError:
        logging.getLogger(__name__).warning("Qdrant readiness deadline exceeded")
        up = False
    if up:
        return ReadinessResponse(dependencies=UpDependencies())
    body = NotReadyResponse(dependencies=DownDependencies())
    return JSONResponse(body.model_dump(), status_code=503)
