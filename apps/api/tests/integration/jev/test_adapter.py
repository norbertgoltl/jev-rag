import asyncio
import json
import logging

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
from jev_rag_api.integrations.jev.adapter import TypeSafeDecisionAdapter


def evaluate(handler, req=None, retries=0):
    async def scenario():
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
def test_real_sdk_wire_contract(language):
    def handler(req):
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
def test_errors_and_bounded_retry(status, error, attempts, caplog):
    calls = []

    def handler(req):
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
def test_transport_errors(exc, error):
    def handler(req):
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
def test_invalid_sdk_responses(mutation):
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

    def handler(req):
        return (
            httpx2.Response(200, content=b"not json")
            if mutation == "invalid_json"
            else httpx2.Response(200, json=data)
        )

    with pytest.raises(DecisionInvalidResponseError):
        evaluate(handler)


def test_sdk_warning_sanitizes_question_names(caplog):
    secret = "secret-user-text"
    data = body()
    data["answers"][secret] = {"type": "future", "value": secret}
    with caplog.at_level(logging.DEBUG, logger="typesafe_sdk"):
        # Adapter construction restores the required WARNING level before any request.
        evaluate(lambda req: httpx2.Response(200, json=data))
    assert secret not in caplog.text
    assert "typesafe_sdk_warning" in caplog.text


def test_no_request_id_and_absent_usage_metadata():
    data = body()
    data["usage"] = {}
    result = evaluate(lambda req: httpx2.Response(200, json=data))
    assert result.provider_request_id is None
    assert result.input_tokens is None and result.output_tokens is None


def test_retry_after_is_honored_without_real_sleep():
    from unittest.mock import AsyncMock

    async def scenario():
        calls = []

        def handler(req):
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


def test_retry_budget_rejects_delay_without_sleep():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx2.Response(429, json={"error": "limited"}, headers={"Retry-After": "20"})

    with pytest.raises(DecisionRateLimitedError):
        evaluate(handler, retries=1)
    assert len(calls) == 1


def test_actual_provider_model_is_preserved():
    data = body()
    data["model"] = "jev-1.14.0"
    assert evaluate(lambda req: httpx2.Response(200, json=data)).model == "jev-1.14.0"
