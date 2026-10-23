from fastapi import APIRouter

from jev_rag_api.api.routes.health import router as health_router
from jev_rag_api.api.routes.system import router as system_router

router = APIRouter()
router.include_router(health_router)
router.include_router(system_router)
