# Backend configuration and error handling

## Configuration

The `Settings` Pydantic Settings model uses this priority order: explicit values, process environment, root `.env`, defaults. The absolute `.env` path is derived from the source file location, not the startup directory. A missing `.env` is allowed, unknown fields are ignored, and Jev settings undergo typed validation. The file is not executed as shell code.

| Variable | Default | Validation |
| --- | --- | --- |
| `APP_ENV` | `development` | `development`, `test`, `production` |
| `APP_DEBUG` | `false` | Must not be true in production |
| `API_HOST` | `127.0.0.1` | Non-empty string |
| `API_PORT` | `8000` | Integer, 1–65535 |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `CORS_ALLOWED_ORIGINS` | `["http://127.0.0.1:3000"]` | JSON array, explicit HTTP(S) origins, no wildcards or paths |
| `QDRANT_URL` | `http://127.0.0.1:6333` | HTTP(S) URL |
| `QDRANT_TIMEOUT_SECONDS` | `1.0` | Positive, finite number |

The template is the root [.env.example](../../.env.example). The backend does not require a TypeSafe key yet. Future secret fields should use `SecretStr`. Settings objects and raw configuration must not enter HTTP responses or logs. The Uvicorn launcher exits with a safe message on invalid configuration.

Setting `APP_DEBUG` to true must not enable public Starlette traceback responses. HTTP debug mode is therefore always disabled. Tests can use `Settings(_env_file=None, ...)` and explicit factory injection.

## Errors, CORS, and request ID

The public error format is `{error: {code, message, details}, request_id}`. `details` is nullable and contains only input locations and error codes for validation errors. It must not include input values, dynamic dictionary keys, SDK responses, or stack traces.

404, 405, 422, 500, and application-level 503 responses follow the [interface contract](../architecture/interface-contracts.md). A 405 preserves the `Allow` header. Readiness dependency failures use a separate diagnostic JSON response and 503. Unknown application errors produce a safe `INTERNAL_ERROR` response.

Every HTTP response receives an `X-Request-ID` header. Incoming IDs may contain 1–64 ASCII letters, digits, dots, underscores, or hyphens. Missing, invalid, or duplicate IDs are replaced by a generated UUID4. The identifier in the error body matches the response header. The `ContextVar` applies throughout the ASGI request and is reset afterward.

Request context and CORS sit outside the Starlette server-error layer, allowing correlation of preflight and 500 responses as well. CORS allows only the configured origin list, GET/OPTIONS, Content-Type/X-Request-ID request headers, and the X-Request-ID exposed header, without credentials.

## Layers and dependencies

The `domain`, `application`, `core`, and `integrations` packages do not import FastAPI or the `api` package. In addition, `domain` and `application` do not import an HTTP client (`httpx`) or `integrations` code. `tests/unit/test_architecture.py` verifies this. HTTP error handling resides in `api/errors.py`. Runtime services are held by the typed `AppContainer` object at `app.state.container` (settings, readiness probe, decision port). Routes access them through the `get_settings`, `get_readiness_probe`, and `get_decision_port` FastAPI dependencies in `api/dependencies.py`. If a service is missing, the dependency raises `ServiceUnavailableError`, producing a `503 SERVICE_UNAVAILABLE` response.

## Structured logging

The standard `logging` JSON formatter writes a UTC ISO timestamp, level, service, event, and request ID. HTTP completion events additionally contain the method, path without query, status, and duration. Unexpected errors log only the exception type, without its message or stack trace.

Request/response bodies, authorization headers, API keys, query strings, document content, and Settings objects must not be logged. The formatter serializes only designated extra fields. After a safe 500 response is complete, the outer middleware handles the re-raised Starlette error so that Uvicorn does not print the raw exception.

The official `jev-rag-api` launcher disables Uvicorn access logs and configures server logs as JSON. Each HTTP request has one completion event. An interrupted streaming response cannot be continued with a new error body.

## Checks

Tests use fake readiness probes and HTTPX/TestClient transports, without Docker or an AI key. Checks should cover both readiness states and timeout, liveness/status without external calls, CORS, configuration priority, 404/405/422/500/503, request IDs and concurrency, and log privacy.

The current execution status is documented in the [API README](../../apps/api/README.md). The 36 pytest tests and the host-based Uvicorn HTTP smoke check passed. The test server was stopped after the latter. Qdrant/Jev remain outside this validation.

FND-018–020 decision integration configuration and testing: [Jev integration](jev-integration.md).
