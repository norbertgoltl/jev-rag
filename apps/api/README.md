# Jev RAG API

Standalone `src/jev_rag_api` project using the `uv_build` build backend and uv-managed CPython `3.14.8`. The virtual environment is located at `apps/api/.venv`. There is no root uv workspace or global project dependency.

## Validation status

The FND-008–011 implementation has been verified: the actual `uv.lock` was created, and the project was installed in editable mode into `apps/api/.venv`. The 36 backend tests, lockfile check, wheel/sdist build, and live HTTP smoke test passed under CPython `3.14.8`.

All five documented endpoints of the running server and the request ID headers were checked. Readiness returns 503 without Qdrant. Server logs use JSON format. The developer CLI smoke tests also passed. Starlette TestClient emits a deprecation warning for the required HTTPX usage, but the tests pass. Migration to HTTPX2 can be a separate dependency change.

## Setup and execution

Resolve dependencies only when explicitly changing dependencies:

```sh
uv lock --project apps/api
```

`apps/api/uv.lock` contains the locked dependencies and must be version-controlled. For normal development, run from the repository root:

```sh
make setup-api
make test-api
make dev-api
```

Commands run exclusively against an existing lockfile in `--locked` mode. `make setup` still requires the frontend manifest and lockfile. `make check` runs the complete quality gate.

Direct checks:

```sh
uv sync --project apps/api --managed-python --locked
uv lock --project apps/api --check
uv run --project apps/api --managed-python --locked pytest
uv run --project apps/api --managed-python --locked python -c 'import jev_rag_api'
uv run --project apps/api --managed-python --locked jev-rag-api
```

The entrypoint starts Uvicorn using the Settings values `API_HOST` and `API_PORT`, defaulting to `127.0.0.1:8000`, with reload in development mode. The application factory is `jev_rag_api.main:create_app(settings=..., readiness_probe=..., decision_port=...)`. Uvicorn invokes it with `factory=True`, so importing the module does not create an application or load configuration. It looks for `.env` in the repository root (next to `pnpm-workspace.yaml`). When used as an installed package without a source checkout, it does not read a dotenv file. If `JEV_MODE` is unset, `Settings.effective_jev_mode` is `mock`, while the `jev_mode` field remains unchanged.

| Endpoint | Expected behavior |
| --- | --- |
| `GET /health/live` | 200, `{"status":"alive"}`, without external calls |
| `GET /health/ready` | Real Qdrant HTTP probe, 200 when ready, otherwise 503 |
| `GET /api/v1/system/status` | 200, `{"service":"api","status":"ok"}` |
| `GET /docs` | Swagger UI |
| `GET /openapi.json` | Generated OpenAPI |

Qdrant readiness uses an HTTPX runtime client. Jev integration is available through a separate DecisionPort adapter. RAG is not implemented yet. Details: [backend development guide](../../docs/development/backend.md), [HTTP contract](../../docs/architecture/interface-contracts.md).

## Jev Decision Layer

The FND-018–020 DecisionPort, mock/live/disabled adapters, TypeSafe SDK 0.7.5, and explicit jev-1.13.0 model are implemented. Offline mock mode with explicit fixtures is active by default. The live client is created once per worker lifecycle and closed at shutdown. Jev does not change the Qdrant readiness contract, and there is no new HTTP endpoint.

`make test-backend` runs offline backend tests with coverage. `make test` runs offline backend and frontend tests. `make jev-smoke` requires separate acceptance of costs with `JEV_LIVE_SMOKE=1`, live mode, and a key. Test commands: [testing](../../docs/development/testing.md). Configuration, errors, and retries: [Jev integration](../../docs/development/jev-integration.md). Contracts: [Decision Layer](../../docs/architecture/decision-layer.md).
