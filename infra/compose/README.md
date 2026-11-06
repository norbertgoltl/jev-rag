# Infrastructure workspace

FND-015–017 implemented the Qdrant configuration in [`../compose.yaml`](../compose.yaml), its named volume, and connectivity and persistence checks in [`../../scripts/infrastructure.py`](../../scripts/infrastructure.py). Run `make up`, `make health`, `make status`, and `make down` from the repository root. `make infra-test` runs the isolated infrastructure acceptance test.

Qdrant may only be published at `127.0.0.1:6333`. Normal shutdown preserves the volume. FastAPI and Next.js run on the host and do not receive application containers.

The infrastructure CLI runs Compose from the repository root with explicit `--env-file .env -f infra/compose.yaml` paths. It reads `.env` with a dotenv parser and never executes it as a shell script. Prerequisites, configuration, and data retention rules are documented in the [infrastructure guide](../../docs/development/infrastructure.md).
