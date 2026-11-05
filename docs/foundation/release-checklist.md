# Foundation release checklist

A row is complete only when its implementation exists and its acceptance evidence is recorded. A plan or documentation entry alone does not prove completion. Use `PASS`, `FAIL`, `NOT RUN`, or `BLOCKED` for each release attempt.

| Scope | Acceptance evidence | Status |
| --- | --- | --- |
| FND-001–004 | Scope, architecture, interface contracts, OpenAPI contract, and ADR-001 are reviewed | See release report |
| FND-005–007 | Monorepo, pinned tooling, Makefile commands, and developer workflow operate | See release report |
| FND-008–011 | FastAPI, settings, logging, errors, and health tests pass | See release report |
| FND-012–014 | Next.js BFF, typed API contracts, diagnostics, lint, typecheck, tests, and build pass | See release report |
| FND-015–017 | Pinned Qdrant, localhost-only port, persistence, readiness, and isolated Compose acceptance pass | See release report |
| FND-018–020 | DecisionPort, deterministic offline adapters, provider contracts, and secret-safe errors pass | See release report |
| FND-021–023 | Backend, frontend, and infrastructure CI jobs pass; `main` requires all checks | See release report |
| FND-024 | Tracked-file, secret, frontend, Docker, and negative security checks pass | See release report |
| FND-025 | Root and scoped agent instructions, workflow, architecture boundaries, and PR contract are usable | See release report |
| FND-026 | Clean setup, integrated health scenarios, quality gates, persistence, CI requirements, and report are evidenced | See release report |

## Release commands

```sh
make doctor
make setup
make up
make check
make security-setup
make security-check
make security-smoke
make infra-test
make down
```

A clean setup must be performed in a separate clone. Do not overwrite an existing `.env`, reset Docker Desktop, delete the normal Qdrant volume, or use `down -v`. `make check` is offline and does not call the live Jev API. A live smoke is optional and requires explicit authorization.

### Isolating the clean clone from the developer environment

Clone outside the working repository (a nested clone shows up as untracked files and is scanned by the working repository's security check). Create the clone's `.env` from `.env.example` only, then set an isolated Docker identity and ports so no developer resource is reused:

```sh
cp .env.example .env
sed -i '' 's/^COMPOSE_PROJECT_NAME=.*/COMPOSE_PROJECT_NAME=jev-rag-release-gate/' .env
sed -i '' 's/^QDRANT_HOST_PORT=.*/QDRANT_HOST_PORT=6343/' .env
sed -i '' 's#^QDRANT_URL=.*#QDRANT_URL=http://127.0.0.1:6343#' .env
sed -i '' 's/^API_PORT=.*/API_PORT=8043/' .env
```

Before starting anything, check that `docker compose --env-file .env -f infra/compose.yaml config` reports `name: jev-rag-release-gate`, published port `6343`, and the volume `jev-rag-release-gate_qdrant_data`, and that `TYPESAFE_API_KEY` is empty (the clone must be secretless; never copy the working repository's `.env`). Start the web server with `BACKEND_API_URL=http://127.0.0.1:8043`. Clean up by name only: `make down`, then `docker volume rm jev-rag-release-gate_qdrant_data`.

## Required GitHub checks

The `main` ruleset must require the exact successful checks `backend`, `frontend`, `infrastructure`, and `security`, with up-to-date branches and pull requests. A failed or missing required check must block merging. Record an actual test PR or ruleset evidence before marking this acceptance item `PASS`. Rulesets and branch protection are not available for a private repository on a free GitHub plan (the API returns HTTP 403); in that case the item stays `BLOCKED` until the repository is public or the plan is upgraded. Verify blocking with a temporary, intentionally failing pull request that is closed without merging; `mergeStateStatus: BLOCKED` on a non-draft PR is sufficient evidence, so do not attempt the merge.

## Final decision

Accept the Foundation only when every required row has passing implementation evidence, the clean-clone procedure succeeds, the four required checks are enforced, and no blocking issue remains. Otherwise mark the release `BLOCKED` or `REJECTED` and list the evidence and next action in `release-report.md`.
