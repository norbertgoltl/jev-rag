# Qdrant infrastructure

Docker Desktop must be installed and started manually. The project uses the explicit desktop-linux context, Linux ARM64 Engine and Docker Compose. Never change the global context or Desktop settings from project scripts. Recommended Desktop resources: 2 CPUs, 4 GiB RAM and 40 GiB disk, Kubernetes disabled.

Copy .env.example to .env only if no local .env exists. From the repository root:

```sh
docker --context desktop-linux compose --env-file .env -f infra/compose.yaml config
docker --context desktop-linux compose --env-file .env -f infra/compose.yaml up -d
docker --context desktop-linux compose --env-file .env -f infra/compose.yaml down
```

Qdrant qdrant/qdrant:v1.19.2 uses linux/arm64, publishes only 127.0.0.1:${QDRANT_HOST_PORT:-6333}:6333 and stores data in the project qdrant_data named volume. No gRPC or cluster port is published. COMPOSE_PROJECT_NAME defaults to jev-rag. QDRANT_URL and QDRANT_TIMEOUT_SECONDS configure the host API. Match QDRANT_URL to the published host port.

Normal down preserves volumes. Never use down -v for development data. Docker Desktop factory reset or data deletion may destroy named volumes. A volume is not a backup. Image upgrades require a separate storage/migration compatibility review. No application collections are created.

## Health and persistence

The read-only Bash helper checks HTTP /readyz and accepts only status 200. The pinned ARM64 image has been verified to support Bash TCP. Health interval is 10s, timeout 3s, retries 5 and start period 15s. FastAPI owns an HTTPX async client in its lifespan and checks Qdrant readiness through the adapter. Network failures and timeouts produce a sanitized structured warning and readiness 503, while liveness remains 200. Readiness recovers to 200 when Qdrant returns. The existing check_health port remains compatible with the new check method.

Validation: 43 backend tests pass. Isolated Docker acceptance during implementation verified collection and point persistence across container recreation, and API readiness 200/503/200. The lifecycle test command is added by FND-017. HTTPX moved from the dev group to runtime without changing package versions.
