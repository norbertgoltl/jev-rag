import pytest

from jev_rag_api.core.config import Settings

# Import the Uvicorn entrypoint in isolation before test-module collection.
# The exported default app must not read a developer's personal dotenv file.
with pytest.MonkeyPatch.context() as patch:
    patch.setitem(Settings.model_config, "env_file", None)
    for field_name in Settings.model_fields:
        patch.delenv(field_name.upper(), raising=False)
    import jev_rag_api.main  # noqa: F401


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, request):
    if request.config.getoption("--jev-live") and "live" in str(request.fspath):
        return
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


@pytest.fixture
def settings():
    return Settings(_env_file=None, app_env="test")


def pytest_addoption(parser):
    parser.addoption("--jev-live", action="store_true", default=False, help="Enable explicitly authorized TypeSafe live smoke")
