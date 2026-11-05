# Foundation release report

## Validation record

- Release candidate: combined FND-024–026 working tree before merge; base `main` commit `9f9f31c`.
- Validation date: 2026-10-31 (Europe/Budapest).
- Target platform: macOS Apple Silicon; CI target is Ubuntu 24.04 x64.
- Python: 3.14.8.
- Node.js: 24.22.1.
- pnpm: 12.15.0.
- Qdrant: `qdrant/qdrant:v1.19.2`.
- Docker: Docker 29.9.2, Compose 5.6.1, Linux ARM64 Engine (local).

## Current results

| Gate | Result | Evidence |
| --- | --- | --- |
| Existing Foundation implementation FND-001–023 | PARTIAL | `make check` and `make infra-test` exercised backend/frontend gates and Qdrant lifecycle. Earlier acceptance documents were reviewed, but not every historical FND acceptance step was rerun. |
| Clean clone: doctor and setup | PASS | Isolated clone: secretless `.env.example`, `make setup`, `make doctor`, and Gitleaks setup all completed successfully. |
| Backend tests, lint, format, strict typecheck | PASS | `make check`; 116 backend tests passed and coverage floor was met. |
| Frontend lint, typecheck, tests, production build | PASS | `make check`; lint, typecheck, 18 tests, coverage floors, and production build passed. |
| Security scanner setup | PASS | Gitleaks 8.30.1 was installed locally and version-checked. |
| Security history scan | PASS | Gitleaks scanned repository history with no finding. |
| Security working-tree scan | PASS | Final `make security-check` scanned history and tracked/untracked first-party project files; no findings. Ignored environment and generated cache files are excluded. |
| Security negative smoke cases | PASS | `make security-smoke` rejected tracked `.env`, frontend secret access, a synthetic credential, and wildcard Qdrant binding. |
| Qdrant security/Compose validation | PASS | `make security-check` verified the pinned image, localhost REST binding, no privileged mode, and no Docker socket mount. |
| Infrastructure acceptance/persistence | PASS | `make infra-test` passed startup, native ARM64, loopback ports, persistence, readiness recovery, idempotency, and context safety; its isolated resources were removed. |
| Integrated API, frontend, and Qdrant scenarios | PASS | Isolated clone: Qdrant healthy, API liveness/readiness returned 200, and Next.js BFF reported backend online/Qdrant up. Services were stopped afterward. |
| GitHub Actions four jobs | PASS for PR #23 | Run [41236569844](https://github.com/norbertgoltl/jev-rag/actions/runs/41236569844) for PR #23: backend, frontend, infrastructure, and security passed. Run [41236616918](https://github.com/norbertgoltl/jev-rag/actions/runs/41236616918) for PR #24 and [41236685665](https://github.com/norbertgoltl/jev-rag/actions/runs/41236685665) for PR #25: backend, frontend, and infrastructure passed. PRs #24 and #25 target `main` before the security workflow is merged, so they do not yet contain the security job. |
| `main` required checks include `security` | BLOCKED | Existing ruleset had `backend`, `frontend`, and `infrastructure`; add `security` after the new job has published a status. |
| GitHub secret scanning and push protection | NOT VERIFIED | The private repository API returned null for these feature fields; confirm availability in repository settings. |

## Acceptance matrix

This release candidate was validated in the current workspace and an isolated local clone. The rows distinguish Foundation implementation evidence from GitHub-hosted CI and branch ruleset evidence, which require publication.

| Group | Status | Evidence needed |
| --- | --- | --- |
| FND-001–004 | PASS, design artifacts reviewed | Scope, architecture, OpenAPI interface contract, and ADR-001 were reviewed. |
| FND-005–007 | PASS | Isolated clone setup and `make doctor` passed with pinned runtimes and developer CLI. |
| FND-008–011 | PASS | Backend Ruff, format, mypy, 116 pytest cases, coverage, and live local liveness/readiness checks passed. |
| FND-012–014 | PASS | Frontend lint, typecheck, 18 tests, coverage, production build, and clean-clone BFF diagnostics passed. |
| FND-015–017 | PASS | `make infra-test` passed architecture, loopback, persistence, readiness recovery, idempotency, and context checks. |
| FND-018–020 | PASS | Offline DecisionPort/TypeSafe adapter tests passed as part of the backend suite; no live key was used. |
| FND-021–023 | PARTIAL | Workflow and local gates pass; PR #23 backend/frontend/infrastructure jobs passed. Required-check enforcement is still unverified. |
| FND-024 | PASS | History/worktree security scan, four negative smoke cases, frontend boundary, and Compose checks passed locally and in the isolated clone; the PR #23 security job also passed. |
| FND-025 | PASS locally | Agent instructions, workflow, architecture boundaries, and PR contract are implemented and exercised by this task. |
| FND-026 | BLOCKED | Clean setup, local quality/security/infrastructure checks, and integrated diagnostics passed. GitHub Actions results, four-check ruleset enforcement, and failed-check merge blocking remain unverified. |

## Known limitations and next actions

1. Merge PR #23 first. Then update PR #24 and PR #25 against the updated `main` and confirm the `security` job passes on both.
2. Update the active `main` ruleset to require all four job names, then verify a failed required check blocks merge.
3. Verify secret scanning and push protection in repository settings if the plan and repository visibility make those features available.
4. Record the post-merge and updated-branch workflow run links.

## Final decision

**BLOCKED.** Local and isolated-clone quality, security, setup, infrastructure, and diagnostics checks passed. PR #23 has all four GitHub Actions jobs passing. Foundation release acceptance still requires the `security` check on the remaining PRs after PR #23 merges, adding it to the `main` required checks, and evidence that failed required checks block merging.

## Erratum: strict mypy gate

The backend type-check gate originally ran `mypy` from the repository root, so `[tool.mypy] strict = true` in `apps/api/pyproject.toml` was not applied and earlier "strict typecheck PASS" results were produced without strict mode. The gate (`make typecheck-backend` and the CI backend job) now passes `--config-file apps/api/pyproject.toml`. Under strict mode the test suite had 157 errors; they are fixed and `mypy` reports no issues in 46 source files.
