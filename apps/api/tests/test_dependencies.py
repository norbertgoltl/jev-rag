from collections.abc import Callable

import pytest
from fastapi import FastAPI

from jev_rag_api.api.dependencies import (
    AppContainer,
    get_decision_port,
    get_readiness_probe,
    get_settings,
)
from jev_rag_api.application.errors import ServiceUnavailableError
from jev_rag_api.core.config import Settings
from jev_rag_api.integrations.jev.mock import MockDecisionAdapter


class AlwaysUpProbe:
    async def check_health(self) -> bool:
        return True


def test_get_settings_returns_container_settings(settings: Settings) -> None:
    assert get_settings(AppContainer(settings=settings)) is settings


def test_get_readiness_probe_returns_configured_probe(settings: Settings) -> None:
    probe = AlwaysUpProbe()
    assert get_readiness_probe(AppContainer(settings=settings, readiness_probe=probe)) is probe


def test_get_decision_port_returns_active_port(settings: Settings) -> None:
    port = MockDecisionAdapter()
    assert get_decision_port(AppContainer(settings=settings, decision_port=port)) is port


@pytest.mark.parametrize("getter", [get_readiness_probe, get_decision_port])
def test_missing_services_raise_service_unavailable(
    settings: Settings, getter: Callable[[AppContainer], object]
) -> None:
    with pytest.raises(ServiceUnavailableError):
        getter(AppContainer(settings=settings))


def test_container_is_attached_to_the_application(settings: Settings) -> None:
    from jev_rag_api.main import create_app

    app: FastAPI = create_app(settings)
    assert isinstance(app.state.container, AppContainer)
    assert app.state.container.settings is settings
