import logging

import httpx

logger = logging.getLogger(__name__)


class QdrantReadinessProbe:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def check_health(self) -> bool:
        try:
            response = await self.client.get("readyz")
        except httpx.RequestError:
            logger.warning("qdrant_unavailable")
            return False
        if response.status_code != 200:
            logger.warning("qdrant_not_ready", extra={"status_code": response.status_code})
            return False
        return True
