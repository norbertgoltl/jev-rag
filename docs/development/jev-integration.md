# Jev / TypeSafe integration

The Python backend's only TypeSafe integration is the `integrations/jev` adapter layer. SDK: `typesafe-sdk==0.7.5`, baseline model: `jev-1.13.0`. The TypeSafe JavaScript SDK is not part of the frontend. Python 3.14's native zstd support is sufficient, with no additional SDK extra.

## Configuration

Configure the root `.env` using the root `.env.example`. Do not overwrite an existing file.

| Variable | Default / rule |
| --- | --- |
| JEV_MODE | development/test: mock. Production requires explicit live or disabled mode, mock is forbidden |
| TYPESAFE_API_KEY | SecretStr, required only in live mode, must not be empty or malformed |
| TYPESAFE_MODEL | jev-1.13.0, floating aliases are not allowed |
| TYPESAFE_TIMEOUT_SECONDS | 5.0, positive and finite |
| TYPESAFE_RETRY_MAX | 1, non-negative integer |
| TYPESAFE_RETRY_BUDGET_SECONDS | 10.0, positive and finite |

The application does not start without a key in live mode or with forbidden production configuration. The key must not enter the frontend, NEXT_PUBLIC variables, or logs. Mock/disabled mode creates no SDK client and makes no external calls. The disabled adapter raises DecisionUnavailableError. There is no mock fallback hiding service failures.

The factory can accept an explicit mock through the `decision_port` argument. The `get_decision_port` dependency can also be overridden using FastAPI dependency_overrides. The default mock has no generic answers: the calling test must supply a fixture for the complete request.

## Timeout, retry, and errors

The Settings timeout, model, and RetryPolicy values are passed directly to the SDK constructor. There is no second application-level retry loop. The SDK uses exponential backoff and honors Retry-After. 400/401/403/422 are not retryable. 429, 529, transient 500/502/503/504, and connection/timeout errors may be retried within bounds. The SDK rejects a next wait that would exceed the remaining budget.

400/422 map to invalid request, 401/403 to authentication, 429 to rate limited, timeouts to timeout, and connection/5xx and all other unknown SDK errors to unavailable domain errors. SDK error mapping uses the SDK's typed exception classes, not the status code attribute. Only 400/422 responses or local failures mapping the request to SDK types produce invalid request errors. Mock adapter fixtures are explicit `(request, result)` pairs matched against the exact complete request. Invalid or missing answers are invalid responses. Domain error messages do not contain SDK exceptions, complete provider bodies, state, or API keys. Client initialization failures produce safe configuration errors.

Structured logs contain the event, request correlation, model identifier, provider request ID, question count and primitive types, duration, optional token counts, and safe error code. State, instructions, and answers must not be logged. The typesafe_sdk logger runs at WARNING level. SDK warning content is replaced with a safe constant event name, preventing leakage of unknown question identifiers or exceptions. TYPESAFE_LOG_LEVEL=debug does not override this after provider initialization.

## Offline validation

```sh
make setup-api
make test-api
make test
make smoke
```

The make test command runs backend and frontend tests. It requires no Docker, Qdrant, API key, or external network. Contract tests for the real SDK use HTTPX2 MockTransport, not a separate REST client. Retry tests use zero wait or mocked async sleep, and the budget test checks behavior without waiting. HU/EN fixtures establish structural compatibility, not equal decision accuracy or calibration.

## Optional live smoke

Live smoke may make a paid external request. Run it only with deliberate authorization, supplying the key through secure environment configuration or the untracked `.env` file.

```sh
JEV_LIVE_SMOKE=1 JEV_MODE=live make jev-smoke
```

The command requires a valid TYPESAFE_API_KEY and an accessible model. It sends a synthetic, non-sensitive state in a single system_one request with category/Choice, urgency/Score, and needs_action/Noul questions. It checks only structure, model identifier, and value ranges, not a specific decision. It does not report mock results as live success. During normal pytest execution, the live test is skipped even if an API key is present in the environment. Both the separate CLI `--jev-live` flag and JEV_LIVE_SMOKE=1 are required.

## Validation results

As of 2026-10-23 (FND-018–020 acceptance), 116 backend tests passed, with 1 explicit live smoke skipped. The frontend's 18 tests and the developer CLI smoke passed. Tests verify primitives, request/result validation, mock determinism, SDK wire format, error mapping, retry/budget behavior, client shutdown, provider/DI, and log protection. Installing the SDK extended backend dependencies and uv.lock, while frontend dependencies remained unchanged.

On 2026-10-23, the explicit live smoke test also passed:

```sh
JEV_LIVE_SMOKE=1 JEV_MODE=live make jev-smoke
```

Result: `1 passed in 0.29s`, exit code 0. A single system_one request through the real TypeSafe SDK successfully verified the structural contract of category/Choice, urgency/Score, and needs_action/Noul primitives, the validity of result values, and the jev-1.13.0 model identifier. This was a live API check, not a mock result. It does not measure decision accuracy or HU/EN quality equivalence. The key and complete provider response were not recorded. Live smoke remains skipped during normal offline test execution.
