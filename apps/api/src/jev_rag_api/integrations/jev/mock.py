import json
from collections.abc import Iterable

from pydantic import ValidationError

from jev_rag_api.domain.decisions.errors import (
    DecisionError,
    DecisionInvalidResponseError,
    DecisionUnavailableError,
)
from jev_rag_api.domain.decisions.models import DecisionRequest, DecisionResult


def _fingerprint(request: DecisionRequest) -> str:
    """Canonical JSON of the full request, so only an identical request matches a fixture."""
    return json.dumps(
        request.model_dump(mode="json"), sort_keys=True, ensure_ascii=True, allow_nan=False
    )


class MockDecisionAdapter:
    """Deterministic DecisionPort that only answers requests it has an explicit fixture for."""

    def __init__(
        self,
        fixtures: Iterable[tuple[DecisionRequest, DecisionResult]] = (),
        error: DecisionError | None = None,
    ) -> None:
        self._fixtures = {_fingerprint(request): result for request, result in fixtures}
        self.error = error

    async def evaluate(self, request: DecisionRequest) -> DecisionResult:
        if self.error is not None:
            raise self.error
        result = self._fixtures.get(_fingerprint(request))
        if result is None:
            raise DecisionInvalidResponseError()
        try:
            return DecisionResult.model_validate(result.model_dump()).validate_for(request)
        except ValidationError, AttributeError:
            raise DecisionInvalidResponseError() from None


class DisabledDecisionAdapter:
    async def evaluate(self, request: DecisionRequest) -> DecisionResult:
        raise DecisionUnavailableError()
