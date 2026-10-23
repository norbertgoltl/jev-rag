from typing import Protocol

from jev_rag_api.domain.decisions.models import DecisionRequest, DecisionResult


class DecisionPort(Protocol):
    async def evaluate(self, request: DecisionRequest) -> DecisionResult: ...
