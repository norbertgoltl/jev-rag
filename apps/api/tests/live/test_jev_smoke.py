import asyncio
import os
from typing import Any

import pytest

from decision_fixtures import request
from jev_rag_api.core.config import Settings
from jev_rag_api.integrations.jev.provider import decision_provider


def test_jev_live_smoke(pytestconfig: pytest.Config) -> None:
    if not pytestconfig.getoption("--jev-live"):
        pytest.skip("Live smoke requires explicit --jev-live authorization")
    if os.environ.get("JEV_LIVE_SMOKE") != "1":
        pytest.fail("Set JEV_LIVE_SMOKE=1 to acknowledge the paid external request")
    settings = Settings()
    if settings.jev_mode != "live" or settings.typesafe_api_key is None:
        pytest.fail("Live smoke requires JEV_MODE=live and TYPESAFE_API_KEY")

    async def scenario() -> Any:
        async with decision_provider(settings) as adapter:
            result = await adapter.evaluate(request())
            assert result.model == settings.typesafe_model
            result.validate_for(request())

    asyncio.run(scenario())


pytestmark = pytest.mark.live
