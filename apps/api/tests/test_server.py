import logging
from typing import Any

import pytest
import uvicorn

from jev_rag_api import main, server
from jev_rag_api.core.logging import (
    JsonFormatter,
    configure_logging,
    json_handler,
    logger,
    uvicorn_log_config,
)


def test_main_module_has_no_import_time_application() -> None:
    assert not hasattr(main, "app")


def test_server_starts_uvicorn_with_the_application_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(uvicorn, "run", lambda target, **kwargs: calls.append(kwargs))
    monkeypatch.setenv("APP_ENV", "test")

    server.main()

    assert len(calls) == 1
    assert calls[0]["factory"] is True
    assert calls[0]["access_log"] is False
    assert calls[0]["reload"] is False


def test_server_rejects_invalid_configuration_without_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_PORT", "secret-value")
    with pytest.raises(SystemExit) as error:
        server.main()
    assert "secret-value" not in str(error.value)


def test_uvicorn_log_config_uses_the_json_formatter() -> None:
    config = uvicorn_log_config()
    assert config["formatters"]["json"]["()"] == f"{JsonFormatter.__module__}.JsonFormatter"
    assert config["loggers"]["uvicorn.access"]["handlers"] == []


def test_configure_logging_is_idempotent() -> None:
    try:
        configure_logging("INFO")
        configure_logging("WARNING")
        assert logger.handlers.count(json_handler()) == 1
        assert logger.level == logging.WARNING
        assert logger.propagate is False
    finally:
        configure_logging("INFO")
