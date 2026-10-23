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

Validation: pinned ARM64 image pulled successfully and Compose configuration validated.
