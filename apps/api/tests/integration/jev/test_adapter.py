import asyncio
import json
import logging

import httpx2
import pytest
import typesafe_sdk as sdk

from decision_fixtures import request, body
from jev_rag_api.integrations.jev.adapter import TypeSafeDecisionAdapter
from jev_rag_api.domain.decisions.errors import (
    DecisionInvalidRequestError, DecisionAuthenticationError, DecisionRateLimitedError,
    DecisionUnavailableError, DecisionTimeoutError, DecisionInvalidResponseError,
)


def evaluate(handler, req=None, retries=0):
    async def scenario():
        async with sdk.AsyncTypeSafeClient(api_key="test-key",model="jev-1.13.0",transport=httpx2.MockTransport(handler),compression=False,retry=sdk.RetryPolicy(max_retries=retries,backoff_initial=0,backoff_max=0,backoff_jitter=0,timeout=1,http_statuses={429,500,502,503,504,529})) as client:
            return await TypeSafeDecisionAdapter(client).evaluate(req or request())
    return asyncio.run(scenario())


@pytest.mark.parametrize("language", ["hu","en"])
def test_real_sdk_wire_contract(language):
    def handler(req):
        sent=json.loads(req.content)
        assert sent["model"]=="jev-1.13.0"
        assert sent["state"]==request(language).state
        assert set(sent["questions"])==set(request().questions)
        assert sent["questions"]["needs_action"]["criteria"]=={"true":"Needs action","false":"No action"}
        return httpx2.Response(200,json=body(),headers={"x-typesafe-request-id":"provider-id"})
    result=evaluate(handler,request(language))
    assert result.model=="jev-1.13.0" and result.provider_request_id=="provider-id"
    assert result.input_tokens==12 and result.output_tokens==4
    assert result.answers["urgency"].score==0.75
    assert result.answers["urgency"].probabilities=={0:0.25,1:0.75}
    assert result.answers["needs_action"].noul==0.9


@pytest.mark.parametrize("status,error,attempts", [(400,DecisionInvalidRequestError,1),(422,DecisionInvalidRequestError,1),(401,DecisionAuthenticationError,1),(403,DecisionAuthenticationError,1),(429,DecisionRateLimitedError,2),(529,DecisionUnavailableError,2),(500,DecisionUnavailableError,2),(503,DecisionUnavailableError,2)])
def test_errors_and_bounded_retry(status,error,attempts,caplog):
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx2.Response(status,json={"error":"private-state-and-api-key"},headers={"Retry-After":"0"})
    with caplog.at_level(logging.WARNING):
        with pytest.raises(error) as caught:evaluate(handler,retries=1)
    assert len(calls)==attempts
    assert "private-state-and-api-key" not in str(caught.value)+caplog.text
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("exc,error", [(httpx2.ConnectError,DecisionUnavailableError),(httpx2.ReadTimeout,DecisionTimeoutError)])
def test_transport_errors(exc,error):
    def handler(req):raise exc("secret-state",request=req)
    with pytest.raises(error) as caught:evaluate(handler)
    assert "secret-state" not in str(caught.value)
