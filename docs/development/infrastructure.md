# Qdrant infrastructure

Installing and starting Docker Desktop is a manual developer prerequisite. No separate runtime or VM manager is required. The project does not reconfigure Docker Desktop or change the global Docker context. The Compose image runs natively on ARM64 Apple Silicon and x64 CI.

## Prerequisites

```sh
docker context inspect desktop-linux
docker --context desktop-linux info
docker --context desktop-linux compose version
cp .env.example .env
make setup-api
make doctor
```

Do not overwrite an existing `.env`. The helper reads it with a dotenv parser and does not execute it as shell code. The doctor checks the Docker Desktop context, Linux Engine architecture, Compose, at least 2 CPUs and 4 GiB of memory, and host port usage. A port used by the project's own running Qdrant is accepted, but a port used by another process is not. Manually verify the recommended 40 GiB virtual disk capacity and disabled Kubernetes in Desktop. The script does not change these settings. The doctor requires an installed backend environment and does not install dependencies.

## Configuration

`infra/compose.yaml` uses the Qdrant `qdrant/qdrant:v1.19.2` image for Docker's native host architecture. The default project name is `jev-rag`, its service is `qdrant`, and data resides in the `jev-rag_qdrant_data` named volume at `/qdrant/storage`. Only the `127.0.0.1:6333` HTTP port is published, with no gRPC or cluster ports exposed. There are no application containers, privileged mode, or Docker socket mounts.

Root `.env` variables: `COMPOSE_PROJECT_NAME`, `QDRANT_HOST_PORT`, `QDRANT_URL`, `QDRANT_TIMEOUT_SECONDS`. When changing ports, update the host port and API URL together. Compose receives explicit `--env-file .env -f infra/compose.yaml` paths and the `--context desktop-linux` context. There is no automatic fallback to another Engine.

## Commands

```sh
make up
make status
make health
make logs
make down
make infra-test
```

The up command validates configuration and waits up to 90 seconds for a healthy state. The logs command follows only the project's Qdrant logs, and Ctrl-C stops it. The health command requests `/readyz` at the configured URL from the host using the configured timeout. Only HTTP 200 is successful. The down command does not delete volumes or images, or stop host applications or Desktop. Repeated up/down is safe. Security requirements: [security baseline](security.md).

The container healthcheck sends a real HTTP request using Bash's built-in TCP functionality and accepts only 200. Interval 10s, timeout 3s, retries 5, start period 15s. The helper is a read-only mount, not a data storage bind mount. Bash and TCP functionality in the pinned image have been verified with a live healthcheck.

## FastAPI readiness

The app lifespan manages one HTTPX AsyncClient. The only public method of QdrantReadinessProbe, the port's `check_health()` method, returns true only for HTTP 200. Timeouts, connection errors, and non-200 responses produce a structured warning (`qdrant_unavailable`, `qdrant_not_ready`) and false. The client closes at shutdown. There is no SDK, collection management, or retrieval.

When Qdrant is available, `/health/ready` returns 200. During an outage it returns 503, while `/health/live` remains 200. After recovery, readiness returns 200 again. Internal URLs and exceptions do not enter responses or warning logs.

## Isolated testing and data retention

The infra-test uses a unique `jev-rag-test-<uuid>` project, a separate free port, and a separate named volume. It writes a test collection and an identifiable point, starts and stops twice, recreates the container, and verifies point persistence and FastAPI's 200 → 503 → 200 behavior. It checks native image architecture, mounts, ports, and that the global context remains unchanged. On success it deletes only its own test volume, also verified through Compose labels. It does not touch the normal developer volume.

On failure, the test prints the project name and preserves resources. Diagnostics: `docker --context desktop-linux compose --env-file .env -f infra/compose.yaml -p <test-project> ps -a`, then `logs qdrant`. Before manual cleanup, verify the test project and the volume's Compose label. Do not use `down -v` in the normal project.

The volume resides in Docker Desktop Engine storage. A factory reset, Desktop data deletion, or targeted volume deletion can cause data loss. A named volume is not a backup. There is no automatic snapshot/restore. Qdrant version upgrades require a separate PR and storage/migration compatibility review.

## Validation

The current [Foundation release report](../foundation/release-report.md) records integration execution results. Earlier checks and the current clean setup status are recorded separately. An earlier run does not replace evidence for each release.
