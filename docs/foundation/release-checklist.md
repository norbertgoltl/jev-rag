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

## Required GitHub checks

The `main` ruleset must require the exact successful checks `backend`, `frontend`, `infrastructure`, and `security`, with up-to-date branches and pull requests. A failed or missing required check must block merging. Record an actual test PR or ruleset evidence before marking this acceptance item `PASS`.

## Final decision

Accept the Foundation only when every required row has passing implementation evidence, the clean-clone procedure succeeds, the four required checks are enforced, and no blocking issue remains. Otherwise mark the release `BLOCKED` or `REJECTED` and list the evidence and next action in `release-report.md`.
