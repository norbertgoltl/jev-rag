from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Request

from jev_rag_api.application.ports.decision import DecisionPort
from jev_rag_api.core.config import Settings
from jev_rag_api.domain.decisions.errors import DecisionConfigurationError
from .mock import DisabledDecisionAdapter, MockDecisionAdapter


def get_decision_port(request: Request) -> DecisionPort:
    return request.app.state.decision_port


@asynccontextmanager
async def decision_provider(settings: Settings, override: DecisionPort | None = None) -> AsyncIterator[DecisionPort]:
    if override is not None:
        yield override
    elif settings.jev_mode == "mock":
        yield MockDecisionAdapter()
    elif settings.jev_mode == "disabled":
        yield DisabledDecisionAdapter()
    else:
        import typesafe_sdk as sdk
        from .adapter import TypeSafeDecisionAdapter, configure_sdk_logging
        configure_sdk_logging()
        try:
            client = sdk.AsyncTypeSafeClient(
                api_key=settings.typesafe_api_key.get_secret_value(),
                model=settings.typesafe_model, timeout=settings.typesafe_timeout_seconds,
                retry=sdk.RetryPolicy(max_retries=settings.typesafe_retry_max, timeout=settings.typesafe_retry_budget_seconds, http_statuses={429, 500, 502, 503, 504, 529}, respect_retry_after=True),
            )
        except (sdk.TypeSafeError, ValueError):
            raise DecisionConfigurationError() from None
        configure_sdk_logging()
        try:
            yield TypeSafeDecisionAdapter(client)
        finally:
            await client.aclose()
