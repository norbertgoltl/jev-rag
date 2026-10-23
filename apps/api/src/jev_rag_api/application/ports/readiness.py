from typing import Protocol


class ReadinessProbe(Protocol):
    async def check_health(self) -> bool: ...


class UnconfiguredReadinessProbe:
    async def check_health(self) -> bool:
        return False
