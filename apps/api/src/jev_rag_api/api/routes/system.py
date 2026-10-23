from fastapi import APIRouter

from jev_rag_api.api.schemas.health import SystemStatusResponse

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/status", response_model=SystemStatusResponse)
async def system_status() -> SystemStatusResponse:
    return SystemStatusResponse()
