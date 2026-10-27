import logging

import httpx

logger = logging.getLogger(__name__)


class QdrantReadinessProbe:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def check(self) -> bool:
        try:
            response = await self.client.get("readyz")
        except httpx.RequestError:
            logger.warning("Qdrant readiness request failed", extra={"event": "qdrant_unavailable"})
            return False
        if response.status_code != 200:
            logger.warning(
                "Qdrant readiness returned non-200",
                extra={"event": "qdrant_not_ready", "status_code": response.status_code},
            )
            return False
        return True

    async def check_health(self) -> bool:
        return await self.check()
