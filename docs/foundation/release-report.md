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

## Re-validation after the code review (2026-11-05)

The Foundation changed after the first record above (strict mypy gate, Prettier and generated contract types, API layering, startup and configuration clean-up, decision adapter clean-up, frontend error handling; PRs #26–#31). The gates were rerun on `main` commit `2298e62` (after PR #31) on macOS Apple Silicon with the same pinned runtimes (Python 3.14.8, Node.js 24.22.1, pnpm 12.15.0, Qdrant `qdrant/qdrant:v1.19.2`, Docker 29.9.2, Compose 5.6.1).

| Gate | Result | Evidence |
| --- | --- | --- |
| `make doctor` | PASS | Pinned tools, Docker, Compose, resources and host port checks passed. |
| `make check` | PASS | Ruff, format, strict mypy (50 source files, config applied), generated API types up to date, 150 backend tests (99% coverage), Prettier, ESLint with zero warnings, tsc, 24 frontend tests (coverage floors met), production build. |
| `make security-setup`, `make security-check`, `make security-smoke` | PASS | Gitleaks 8.30.1 history and working-tree scans, frontend and Qdrant boundaries, and all four negative cases were rejected. |
| `make infra-test` | PASS | Startup, native ARM64, loopback ports, persistence, readiness recovery, idempotency and context safety. Its isolated project, network and volume were removed; no developer volume was touched. |
| Integrated scenario (current checkout) | PASS | `make up`, API on 8000 and Next.js on 3000: readiness 200 with Qdrant up and the BFF reported backend online, readiness `ready`, Qdrant `up`. After `make down` (volume preserved) readiness returned 503 and the BFF reported readiness `not_ready`, Qdrant `down` while liveness stayed 200. Services were stopped afterwards. |
| Clean clone: setup and doctor | NOT RUN | The clean-clone procedure was not repeated: creating the separate clone was blocked in the automated session. Run it manually (see the release checklist). The first record above remains the latest clean-clone evidence, for an earlier commit. |
| GitHub Actions on pull requests #26–#31 | PASS with one exception | `backend`, `frontend`, `infrastructure` and `security` passed on #26, #27, #29, #30 and #31. On #28 the run (42067447169) was created at 16:43:54Z, after the PR was merged at 16:40:40Z; three jobs passed and the `frontend` job stayed `in_progress` with the run still `queued`. This coincides with the GitHub Actions incident described below, and the run cannot be cancelled (HTTP 409) or deleted (HTTP 403) by the repository owner. |
| GitHub Actions on `main` | PASS with one exception | The push run for the #31 merge (run [42087895091](https://github.com/norbertgoltl/jev-rag/actions/runs/42087895091)) passed all four jobs, as did the runs for #26, #27, #29 and #30. The run for the #28 merge commit `6924a7d` ended in `startup_failure` at 16:44:55Z with no jobs (the run was created and completed in the same second); the following commits passed. This also coincides with the GitHub Actions incident described below. |
| `main` required checks include all four jobs | PASS while public; not applicable while private | While the repository was private the rulesets API returned HTTP 403. After the repository was made public the active ruleset `Protect main` required only `backend`, `frontend` and `infrastructure`; `security` was added on 2026-11-05. The ruleset now requires all four checks with up-to-date branches, pull requests, no deletion and no force push, and has no bypass actors. |
| Failed or missing required check blocks merge | PASS while public; FAIL while private | After the repository returned to private, test PR #36 (same intentionally failing test, closed without merging, branch deleted) was reported as `mergeStateStatus: UNSTABLE` (`mergeable_state: unstable`), not `BLOCKED`: the failing `backend` check is not treated as required, so the ruleset is not enforced while the repository is private on the current plan. The rulesets API again returns HTTP 403. The public-state evidence follows. PR #28 had been merged while its `frontend` check was still queued, before enforcement was available. Test PR #33 contained one intentionally failing test: `backend` failed, the other three checks passed, and GitHub reported `mergeStateStatus: BLOCKED` (`mergeable_state: blocked`) for a non-draft PR. A merge was deliberately not attempted. The PR was closed without merging and its branch deleted. |
| GitHub secret scanning and push protection | PASS while public; NOT VERIFIED while private | After the repository became public the API reports `secret_scanning` and `secret_scanning_push_protection` as `enabled`. While private the API again reports no `security_and_analysis` data. The Gitleaks history and working-tree scans in `make security-check` and the CI `security` job are unaffected. |

### Decision after re-validation

**BLOCKED.** The code is in better shape than at the first record: strict type checking now actually runs, the layers are separated, the contract types are generated and checked, and every local and CI gate passed on the merged state. Required checks are enforced and verified only while the repository is public (see the measurements above); in the current private state they are not enforced. The release is still blocked on remaining evidence:

1. Rerun the clean-clone setup (`make setup`, `make doctor`, security setup) and the integrated scenario in a separate clone, as described in the release checklist. This was NOT RUN because creating the clone was blocked in the automated session.
2. ~~Investigate the queued `frontend` run on PR #28 and the `startup_failure` on `main` commit `6924a7d`.~~ Investigated on 2026-11-05: both are attributed to the GitHub [Actions incident](https://www.githubstatus.com/incidents/t89g2q1800fr) (first reported 16:50 UTC: "workflow runs may experience delays or errors when starting"; mitigated 17:04 UTC; resolved 17:42 UTC). The evidence is circumstantial: the two events happened at 16:43-16:45 UTC, a few minutes before the first public report, and the incident page does not mention stuck jobs, so the stuck `frontend` job is an inference. Neither event reproduced on PRs #29-#34 or later `main` runs, and the merged code was covered by the following runs and the local gates. The orphaned run 42067447169 cannot be cancelled or deleted by the repository owner; it is harmless (it belongs to a merged PR) and can only be removed by GitHub support or by expiry.
3. Enforcement of the four required checks needs either a public repository or a GitHub plan that supports rulesets on private repositories. The repository is currently private on the current plan and was measured as not enforcing them (test PR #36). Until one of these is chosen, merges are protected only by convention and by the CI results being visible on each pull request. Do not merge a pull request with a failing or missing check.

## Erratum: strict mypy gate

The backend type-check gate originally ran `mypy` from the repository root, so `[tool.mypy] strict = true` in `apps/api/pyproject.toml` was not applied and earlier "strict typecheck PASS" results were produced without strict mode. The gate (`make typecheck-backend` and the CI backend job) now passes `--config-file apps/api/pyproject.toml`. Under strict mode the test suite had 157 errors; they are fixed and `mypy` reports no issues in 46 source files.
