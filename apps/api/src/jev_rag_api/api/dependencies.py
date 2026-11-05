from dataclasses import dataclass

from fastapi import Depends, Request

from jev_rag_api.application.errors import ServiceUnavailableError
from jev_rag_api.application.ports.decision import DecisionPort
from jev_rag_api.application.ports.readiness import ReadinessProbe
from jev_rag_api.core.config import Settings


@dataclass
class AppContainer:
    """Typed runtime services of one application instance.

    ``readiness_probe`` and ``decision_override`` may be injected by the application factory.
    ``decision_port`` is only set while the application lifespan is running.
    """

    settings: Settings
    readiness_probe: ReadinessProbe | None = None
    decision_override: DecisionPort | None = None
    decision_port: DecisionPort | None = None


def get_container(request: Request) -> AppContainer:
    container: AppContainer = request.app.state.container
    return container


def get_settings(container: AppContainer = Depends(get_container)) -> Settings:
    return container.settings


def get_readiness_probe(container: AppContainer = Depends(get_container)) -> ReadinessProbe:
    if container.readiness_probe is None:
        raise ServiceUnavailableError("Readiness probe is not available")
    return container.readiness_probe


def get_decision_port(container: AppContainer = Depends(get_container)) -> DecisionPort:
    if container.decision_port is None:
        raise ServiceUnavailableError("Decision port is not available")
    return container.decision_port
