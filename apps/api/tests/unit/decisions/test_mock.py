import asyncio
from typing import Any

import pytest

from decision_fixtures import request, result
from jev_rag_api.domain.decisions.errors import (
    DecisionInvalidResponseError,
    DecisionUnavailableError,
)
from jev_rag_api.integrations.jev.mock import DisabledDecisionAdapter, MockDecisionAdapter


@pytest.mark.parametrize("language", ["hu", "en"])
def test_deterministic_fixture(language: Any) -> None:
    req = request(language)
    adapter = MockDecisionAdapter({MockDecisionAdapter.key(req): result()})
    assert asyncio.run(adapter.evaluate(req)) == asyncio.run(adapter.evaluate(req)) == result()
    with pytest.raises(DecisionInvalidResponseError):
        asyncio.run(adapter.evaluate(request("hu" if language == "en" else "en")))


def test_missing_fixture() -> None:
    with pytest.raises(DecisionInvalidResponseError):
        asyncio.run(MockDecisionAdapter().evaluate(request()))


def test_configured_domain_error() -> None:
    with pytest.raises(DecisionUnavailableError):
        asyncio.run(MockDecisionAdapter(error=DecisionUnavailableError()).evaluate(request()))


def test_disabled() -> None:
    with pytest.raises(DecisionUnavailableError):
        asyncio.run(DisabledDecisionAdapter().evaluate(request()))


def test_invalid_mutated_fixture_is_not_accepted() -> None:
    req = request()
    fixture = result()
    fixture.answers["needs_action"].__dict__["noul"] = float("nan")
    adapter = MockDecisionAdapter({MockDecisionAdapter.key(req): fixture})
    with pytest.raises(DecisionInvalidResponseError):
        asyncio.run(adapter.evaluate(req))
