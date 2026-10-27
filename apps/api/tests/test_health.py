import asyncio

import pytest
from fastapi.testclient import TestClient

from jev_rag_api.main import create_app


class FakeProbe:
    def __init__(self, up):
        self.up = up
        self.calls = 0

    async def check_health(self):
        self.calls += 1
        return self.up


@pytest.mark.parametrize(
    "up, status, body",
    [
        (True, 200, {"status": "ready", "dependencies": {"qdrant": "up"}}),
        (False, 503, {"status": "not_ready", "dependencies": {"qdrant": "down"}}),
    ],
)
def test_readiness(settings, up, status, body):
    probe = FakeProbe(up)
    with TestClient(create_app(settings, probe)) as client:
        response = client.get("/health/ready")
    assert response.status_code == status
    assert response.json() == body
    assert probe.calls == 1


def test_liveness_and_status_do_not_call_dependencies(settings):
    probe = FakeProbe(False)
    with TestClient(create_app(settings, probe)) as client:
        assert client.get("/health/live").json() == {"status": "alive"}
        assert client.get("/api/v1/system/status").json() == {"service": "api", "status": "ok"}
    assert probe.calls == 0


def test_unconfigured_readiness(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/ready").status_code == 503


def test_readiness_timeout(settings):
    class SlowProbe:
        async def check_health(self):
            await asyncio.sleep(10)
            return True

    settings.qdrant_timeout_seconds = 0.001
    with TestClient(create_app(settings, SlowProbe())) as client:
        assert client.get("/health/ready").status_code == 503
