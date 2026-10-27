from pydantic import ValidationError

from jev_rag_api.domain.decisions.errors import (
    DecisionError,
    DecisionInvalidResponseError,
    DecisionUnavailableError,
)
from jev_rag_api.domain.decisions.models import DecisionRequest, DecisionResult


class MockDecisionAdapter:
    def __init__(
        self, fixtures: dict[str, DecisionResult] | None = None, error: DecisionError | None = None
    ) -> None:
        self.fixtures = fixtures or {}
        self.error = error

    @staticmethod
    def key(request: DecisionRequest) -> str:
        import json

        return json.dumps(
            request.model_dump(mode="json"), sort_keys=True, ensure_ascii=True, allow_nan=False
        )

    async def evaluate(self, request: DecisionRequest) -> DecisionResult:
        if self.error is not None:
            raise self.error
        result = self.fixtures.get(self.key(request))
        if result is None:
            raise DecisionInvalidResponseError()
        try:
            return DecisionResult.model_validate(result.model_dump()).validate_for(request)
        except ValidationError, AttributeError:
            raise DecisionInvalidResponseError() from None


class DisabledDecisionAdapter:
    async def evaluate(self, request: DecisionRequest) -> DecisionResult:
        raise DecisionUnavailableError()
