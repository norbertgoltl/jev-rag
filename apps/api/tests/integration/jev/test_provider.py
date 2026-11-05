import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import ValidationError

from jev_rag_api.api.dependencies import get_decision_port
from jev_rag_api.application.ports.decision import DecisionPort
from jev_rag_api.integrations.jev.mock import DisabledDecisionAdapter, MockDecisionAdapter
from jev_rag_api.integrations.jev.provider import decision_provider
from jev_rag_api.main import create_app
from settings_factory import build_settings


@pytest.mark.parametrize(
    "values",
    [
        {"jev_mode": "live"},
        {"jev_mode": "live", "typesafe_api_key": " "},
        {"app_env": "production"},
        {"app_env": "production", "jev_mode": "mock"},
        {"typesafe_model": "jev-latest"},
        {"typesafe_retry_max": -1},
        {"typesafe_timeout_seconds": 0},
        {"typesafe_retry_budget_seconds": float("inf")},
    ],
)
def test_invalid_configuration(values: Any) -> None:
    with pytest.raises(ValidationError):
        build_settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "mode,kind", [("mock", MockDecisionAdapter), ("disabled", DisabledDecisionAdapter)]
)
def test_offline_modes_never_construct_sdk_client(
    mode: Any, kind: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import typesafe_sdk as sdk

    constructor = Mock(side_effect=AssertionError("SDK construction forbidden"))
    monkeypatch.setattr(sdk, "AsyncTypeSafeClient", constructor)

    async def scenario() -> Any:
        async with decision_provider(build_settings(_env_file=None, jev_mode=mode)) as adapter:
            assert isinstance(adapter, kind)

    asyncio.run(scenario())
    constructor.assert_not_called()


def test_live_client_shared_and_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import typesafe_sdk as sdk

    client = Mock(aclose=AsyncMock())
    constructor = Mock(return_value=client)
    monkeypatch.setattr(sdk, "AsyncTypeSafeClient", constructor)
    app = create_app(build_settings(_env_file=None, jev_mode="live", typesafe_api_key="test-key"))
    with TestClient(app) as api:
        assert app.state.container.decision_port.client is client
        assert api.get("/health/live").status_code == 200
        assert app.state.container.decision_port.client is client
    constructor.assert_called_once()
    client.aclose.assert_awaited_once()
    kwargs = constructor.call_args.kwargs
    assert kwargs["model"] == "jev-1.13.0" and kwargs["timeout"] == 5
    assert kwargs["retry"].max_retries == 1 and kwargs["retry"].timeout == 10
    assert kwargs["retry"].respect_retry_after is True
    assert {429, 529}.issubset(kwargs["retry"].http_statuses)
    assert {400, 401, 403, 422}.isdisjoint(kwargs["retry"].http_statuses)


def test_factory_and_fastapi_dependency_override() -> None:
    adapter = MockDecisionAdapter()
    app = create_app(build_settings(_env_file=None), decision_port=adapter)

    @app.get("/test-decision-provider")
    async def endpoint(port: DecisionPort = Depends(get_decision_port)) -> Any:
        return {"mock": port is adapter}

    with TestClient(app) as api:
        assert api.get("/test-decision-provider").json() == {"mock": True}
        alternate = DisabledDecisionAdapter()
        app.dependency_overrides[get_decision_port] = lambda: alternate
        assert api.get("/test-decision-provider").json() == {"mock": False}
    assert app.state.container.decision_port is None


def test_secret_not_in_settings_representation_or_json() -> None:
    settings = build_settings(_env_file=None, jev_mode="live", typesafe_api_key="super-secret")
    assert "super-secret" not in repr(settings)
    assert "super-secret" not in settings.model_dump_json()


def test_client_closed_when_lifespan_body_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    import typesafe_sdk as sdk

    client = Mock(aclose=AsyncMock())
    monkeypatch.setattr(sdk, "AsyncTypeSafeClient", Mock(return_value=client))

    async def scenario() -> Any:
        with pytest.raises(RuntimeError):
            async with decision_provider(
                build_settings(_env_file=None, jev_mode="live", typesafe_api_key="test-key")
            ):
                raise RuntimeError("startup failed")

    asyncio.run(scenario())
    client.aclose.assert_awaited_once()


def test_production_disabled_allowed() -> None:
    assert (
        build_settings(_env_file=None, app_env="production", jev_mode="disabled").jev_mode
        == "disabled"
    )


def test_sdk_constructor_error_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    import typesafe_sdk as sdk

    from jev_rag_api.domain.decisions.errors import DecisionConfigurationError

    monkeypatch.setattr(
        sdk, "AsyncTypeSafeClient", Mock(side_effect=sdk.TypeSafeError("secret-key"))
    )

    async def scenario() -> Any:
        with pytest.raises(DecisionConfigurationError) as caught:
            async with decision_provider(
                build_settings(_env_file=None, jev_mode="live", typesafe_api_key="test-key")
            ):
                pass
        assert "secret-key" not in str(caught.value)

    asyncio.run(scenario())


def test_real_sdk_transport_is_closed_on_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx2
    import typesafe_sdk as sdk

    original = sdk.AsyncTypeSafeClient
    created = []

    def factory(**kwargs: Any) -> Any:
        client = original(
            **kwargs, transport=httpx2.MockTransport(lambda request: httpx2.Response(200, json={}))
        )
        created.append(client)
        return client

    monkeypatch.setattr(sdk, "AsyncTypeSafeClient", factory)
    with TestClient(
        create_app(build_settings(_env_file=None, jev_mode="live", typesafe_api_key="test-key"))
    ):
        assert len(created) == 1 and not created[0]._http_client.is_closed
    assert created[0]._http_client.is_closed
