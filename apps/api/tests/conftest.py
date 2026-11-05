import pytest

from jev_rag_api.core.config import Settings
from settings_factory import build_settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if request.config.getoption("--jev-live") and "live" in str(request.path):
        return
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


@pytest.fixture
def settings() -> Settings:
    return build_settings(_env_file=None, app_env="test")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--jev-live",
        action="store_true",
        default=False,
        help="Enable explicitly authorized TypeSafe live smoke",
    )
