# Infrastructure troubleshooting

- Docker Desktop missing or stopped: install/start it manually, then run `make doctor`. The project does not start it automatically.
- Missing `desktop-linux` context: check the Desktop Linux Engine setting. There is no fallback to another Engine or global context switch.
- Engine/image architecture error: macOS Apple Silicon requires a native ARM64 image, and x64 Linux CI requires a native x64 image. Do not force emulation.
- Port in use: `lsof -nP -iTCP:6333 -sTCP:LISTEN`. Do not automatically stop another process. Set a separate QDRANT_HOST_PORT and matching QDRANT_URL.
- Image pull failure: check Docker Hub connectivity, then repeat the up command. There is no floating-tag fallback.
- Unhealthy/startup timeout: `make status`, `make logs`. Check the healthcheck's read-only helper mount and volume write permissions. Do not delete the volume as a fix.
- FastAPI readiness 503: run `make health`, then check the backend QDRANT_URL and timeout. Liveness remains 200 even during a Qdrant outage.
- Failed infra-test: the printed unique project and volume remain available for diagnosis. Cleanup boundaries are documented in the [infrastructure runbook](infrastructure.md).
- Docker Desktop reset/data deletion: can cause data loss, and a named volume is not a backup. The project does not perform resets or automatic recovery.
- Security check stops with a Gitleaks error: run `make security-setup`, check the network and supported platform, then rerun `make security-check`. Do not expose secret values in the printed report.
- Security scanner finding: treat the credential as compromised, revoke or rotate it, then follow the [security incident procedure](security.md#incident-procedure). Removal alone does not revoke a previously leaked key.
