from fastapi import APIRouter

from jev_rag_api.api.routes.health import router as health_router
from jev_rag_api.api.routes.system import router as system_router
from jev_rag_api.api.schemas.errors import ErrorResponse

request_id_header = {
    "X-Request-ID": {
        "description": "Request correlation identifier",
        "schema": {"type": "string", "pattern": "^[A-Za-z0-9._-]{1,64}$"},
    }
}
router = APIRouter(
    responses={
        200: {"headers": request_id_header},
        503: {"headers": request_id_header},
        500: {"model": ErrorResponse, "headers": request_id_header},
    }
)
router.include_router(health_router)
router.include_router(system_router)
