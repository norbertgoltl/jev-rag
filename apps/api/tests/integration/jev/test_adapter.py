import asyncio
import json
import logging
from typing import Any

import httpx2
import pytest
import typesafe_sdk as sdk

from decision_fixtures import body, request
from jev_rag_api.domain.decisions.errors import (
    DecisionAuthenticationError,
    DecisionInvalidRequestError,
    DecisionInvalidResponseError,
    DecisionRateLimitedError,
    DecisionTimeoutError,
    DecisionUnavailableError,
)
from jev_rag_api.integrations.jev.adapter import TypeSafeDecisionAdapter, translate_sdk_error


def evaluate(handler: Any, req: Any = None, retries: Any = 0) -> Any:
    async def scenario() -> Any:
        async with sdk.AsyncTypeSafeClient(
            api_key="test-key",
            model="jev-1.13.0",
            transport=httpx2.MockTransport(handler),
            compression=False,
            retry=sdk.RetryPolicy(
                max_retries=retries,
                backoff_initial=0,
                backoff_max=0,
                backoff_jitter=0,
                timeout=1,
                http_statuses={429, 500, 502, 503, 504, 529},
            ),
        ) as client:
            return await TypeSafeDecisionAdapter(client).evaluate(req or request())

    return asyncio.run(scenario())


@pytest.mark.parametrize("language", ["hu", "en"])
def test_real_sdk_wire_contract(language: Any) -> None:
    def handler(req: Any) -> Any:
        sent = json.loads(req.content)
        assert sent["model"] == "jev-1.13.0"
        assert sent["state"] == request(language).state
        assert set(sent["questions"]) == set(request().questions)
        assert sent["questions"]["needs_action"]["criteria"] == {
            "true": "Needs action",
            "false": "No action",
        }
        return httpx2.Response(200, json=body(), headers={"x-typesafe-request-id": "provider-id"})

    result = evaluate(handler, request(language))
    assert result.model == "jev-1.13.0" and result.provider_request_id == "provider-id"
    assert result.input_tokens == 12 and result.output_tokens == 4
    assert result.answers["urgency"].score == 0.75
    assert result.answers["urgency"].probabilities == {0: 0.25, 1: 0.75}
    assert result.answers["needs_action"].noul == 0.9


@pytest.mark.parametrize(
    "status,error,attempts",
    [
        (400, DecisionInvalidRequestError, 1),
        (422, DecisionInvalidRequestError, 1),
        (401, DecisionAuthenticationError, 1),
        (403, DecisionAuthenticationError, 1),
        (429, DecisionRateLimitedError, 2),
        (529, DecisionUnavailableError, 2),
        (500, DecisionUnavailableError, 2),
        (503, DecisionUnavailableError, 2),
    ],
)
def test_errors_and_bounded_retry(
    status: Any, error: Any, attempts: Any, caplog: pytest.LogCaptureFixture
) -> None:
    calls = []

    def handler(req: Any) -> Any:
        calls.append(req)
        return httpx2.Response(
            status, json={"error": "private-state-and-api-key"}, headers={"Retry-After": "0"}
        )

    with caplog.at_level(logging.WARNING):
        with pytest.raises(error) as caught:
            evaluate(handler, retries=1)
    assert len(calls) == attempts
    assert "private-state-and-api-key" not in str(caught.value) + caplog.text
    assert caught.value.__cause__ is None


@pytest.mark.parametrize(
    "exc,error",
    [(httpx2.ConnectError, DecisionUnavailableError), (httpx2.ReadTimeout, DecisionTimeoutError)],
)
def test_transport_errors(exc: Any, error: Any) -> None:
    def handler(req: Any) -> Any:
        raise exc("secret-state", request=req)

    with pytest.raises(error) as caught:
        evaluate(handler)
    assert "secret-state" not in str(caught.value)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "unknown",
        "invalid",
        "wrong_type",
        "wrong_choice",
        "wrong_scale",
        "invalid_json",
    ],
)
def test_invalid_sdk_responses(mutation: Any) -> None:
    data = body()
    if mutation == "missing":
        del data["answers"]["category"]
    if mutation == "extra":
        data["answers"]["extra"] = {"type": "noul", "noul": 0.5}
    if mutation == "unknown":
        data["answers"]["category"] = {"type": "future", "value": 1}
    if mutation == "invalid":
        data["answers"]["needs_action"]["noul"] = 1.1
    if mutation == "wrong_type":
        data["answers"]["category"] = {"type": "noul", "noul": 0.5}
    if mutation == "wrong_choice":
        data["answers"]["category"]["choice"] = "unknown"
    if mutation == "wrong_scale":
        data["answers"]["urgency"]["score"] = 3.0

    def handler(req: Any) -> Any:
        return (
            httpx2.Response(200, content=b"not json")
            if mutation == "invalid_json"
            else httpx2.Response(200, json=data)
        )

    with pytest.raises(DecisionInvalidResponseError):
        evaluate(handler)


def test_sdk_warning_sanitizes_question_names(caplog: pytest.LogCaptureFixture) -> None:
    secret = "secret-user-text"
    data = body()
    data["answers"][secret] = {"type": "future", "value": secret}
    with caplog.at_level(logging.DEBUG, logger="typesafe_sdk"):
        # Adapter construction restores the required WARNING level before any request.
        evaluate(lambda req: httpx2.Response(200, json=data))
    assert secret not in caplog.text
    assert "typesafe_sdk_warning" in caplog.text


def test_no_request_id_and_absent_usage_metadata() -> None:
    data = body()
    data["usage"] = {}
    result = evaluate(lambda req: httpx2.Response(200, json=data))
    assert result.provider_request_id is None
    assert result.input_tokens is None and result.output_tokens is None


def test_retry_after_is_honored_without_real_sleep() -> None:
    from unittest.mock import AsyncMock

    async def scenario() -> Any:
        calls = []

        def handler(req: Any) -> Any:
            calls.append(req)
            return (
                httpx2.Response(429, json={"error": "limited"}, headers={"Retry-After": "2"})
                if len(calls) == 1
                else httpx2.Response(200, json=body())
            )

        async with sdk.AsyncTypeSafeClient(
            api_key="test-key",
            model="jev-1.13.0",
            transport=httpx2.MockTransport(handler),
            retry=sdk.RetryPolicy(max_retries=1, timeout=10),
        ) as client:
            sleep = AsyncMock()
            client._retry.sleep = sleep
            result = await TypeSafeDecisionAdapter(client).evaluate(request())
            assert result.model == "jev-1.13.0" and len(calls) == 2
            sleep.assert_awaited_once()
            assert float(sleep.call_args.args[0]) == 2.0

    asyncio.run(scenario())


def test_retry_budget_rejects_delay_without_sleep() -> None:
    calls = []

    def handler(req: Any) -> Any:
        calls.append(req)
        return httpx2.Response(429, json={"error": "limited"}, headers={"Retry-After": "20"})

    with pytest.raises(DecisionRateLimitedError):
        evaluate(handler, retries=1)
    assert len(calls) == 1


def test_actual_provider_model_is_preserved() -> None:
    data = body()
    data["model"] = "jev-1.14.0"
    assert evaluate(lambda req: httpx2.Response(200, json=data)).model == "jev-1.14.0"


@pytest.mark.parametrize(
    "sdk_error,expected",
    [
        (sdk.TypeSafeBadRequestError, DecisionInvalidRequestError),
        (sdk.TypeSafeUnprocessableEntityError, DecisionInvalidRequestError),
        (sdk.TypeSafeAuthenticationError, DecisionAuthenticationError),
        (sdk.TypeSafePermissionDeniedError, DecisionAuthenticationError),
        (sdk.TypeSafeRateLimitError, DecisionRateLimitedError),
        (sdk.TypeSafeNotFoundError, DecisionUnavailableError),
        (sdk.TypeSafeInternalServerError, DecisionUnavailableError),
        (sdk.TypeSafeAPITimeoutError, DecisionTimeoutError),
        (sdk.TypeSafeAPIConnectionError, DecisionUnavailableError),
        (sdk.TypeSafeAPIResponseValidationError, DecisionInvalidResponseError),
    ],
)
def test_sdk_error_types_map_to_domain_errors(sdk_error: Any, expected: Any) -> None:
    assert type(translate_sdk_error(sdk_error.__new__(sdk_error))) is expected


def test_unknown_sdk_error_is_provider_unavailable_not_invalid_request() -> None:
    assert type(translate_sdk_error(sdk.TypeSafeError())) is DecisionUnavailableError


def test_request_mapping_failure_is_invalid_request(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(request: Any) -> Any:
        raise sdk.TypeSafeError("secret-state")

    monkeypatch.setattr("jev_rag_api.integrations.jev.adapter.map_questions", reject)
    calls: list[Any] = []

    def handler(req: Any) -> Any:
        calls.append(req)
        return httpx2.Response(200, json=body())

    with pytest.raises(DecisionInvalidRequestError) as caught:
        evaluate(handler)
    assert "secret-state" not in str(caught.value)
    assert calls == []
