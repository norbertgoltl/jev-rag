# Security baseline

## Configuration ownership

The root `.env` is read by Docker Compose and the FastAPI process. `apps/web/.env.local` belongs to Next.js only. Neither application reads the other application's local file. Keep the safe templates `.env.example` and `apps/web/.env.local.example` in Git. `.gitignore` excludes actual environment files, but it is not a secret scanner.

| Variable | Owner | Sensitive | Notes |
| --- | --- | --- | --- |
| `TYPESAFE_API_KEY` | FastAPI | Yes | Required only in `JEV_MODE=live`; represented as Pydantic `SecretStr` |
| `JEV_MODE` | FastAPI | No | `mock`, `live`, or `disabled`; production rejects mock |
| `TYPESAFE_MODEL` | FastAPI | No | Pinned provider model identifier |
| `QDRANT_URL` | FastAPI | No | Local Qdrant URL |
| `QDRANT_TIMEOUT_SECONDS` | FastAPI | No | Positive readiness timeout |
| `APP_ENV`, `APP_DEBUG` | FastAPI | No | Production debug mode is rejected |
| `BACKEND_API_URL` | Next.js server | No | Internal URL; never expose through `NEXT_PUBLIC_*` or `next.config.*` `env` |
| `BACKEND_TIMEOUT_MS` | Next.js server | No | Positive request timeout |
| `QDRANT_HOST_PORT` | Docker Compose | No | Qdrant REST host port; bound to loopback |

`SecretStr` masks ordinary display and JSON serialization. Convert it to plaintext only where the provider SDK client is constructed. Never log authorization headers, API keys, request bodies, raw provider responses, or tracebacks in public errors. Normal tests run in mock mode and do not require a live key.

## Network and browser boundaries

FastAPI and Next.js run on the host. Qdrant runs in Docker Compose and exposes only REST on `127.0.0.1:6333`; it does not publish gRPC or cluster ports. The Qdrant image is pinned, runs without privileged mode, and receives no Docker socket. The Next.js BFF uses a server-only module to read its backend URL. Browser code communicates with the BFF and must not call FastAPI, Qdrant, or Jev directly.

## Automated checks

Install the pinned project-local Gitleaks scanner and run the checks:

```sh
make security-setup
make security-check
make security-smoke
```

The scanner is Gitleaks 8.30.1. The setup script supports macOS ARM64/x64 and Linux ARM64/x64, downloads the official release asset, and verifies its pinned SHA-256 before installing under ignored `.tools/`. The security check scans repository history and first-party working-tree paths, checks tracked secret-like files, validates frontend boundaries and the effective Qdrant Compose configuration. The smoke test proves that synthetic failures are rejected. Scanner errors or missing binaries fail the gate.

GitHub Actions runs `security` without a Jev API key. The `main` ruleset must require the named `security` status check in addition to `backend`, `frontend`, and `infrastructure` after that status has been published by CI. Repository secret-scanning and push-protection availability is controlled by GitHub repository features; review their state in repository settings when available.

## Incident procedure

If a credential may have entered Git or a build artifact:

1. Revoke or rotate the credential at its provider immediately. Removing it from the current tree does not make an exposed key safe.
2. Notify the repository maintainer and identify affected commits, pull requests, logs, and artifacts without copying the value into an issue.
3. Run `make security-check` and inspect only redacted scanner metadata. Do not paste secret values into terminal transcripts or PR comments.
4. Remove the credential from active configuration and replace it with an environment variable or an approved secret store. Use history rewriting only through a separately authorized incident procedure.
5. Re-run the security and relevant application checks, confirm the old key is revoked, and record the incident outcome without retaining the secret.

Production identity, a secrets vault, public deployment, penetration testing, and automated backup/restore are outside this Foundation baseline.
