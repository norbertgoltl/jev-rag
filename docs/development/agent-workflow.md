# Coding agent workflow

## Before editing

1. Read the task, the root `AGENTS.md`, relevant directory-level instructions, architecture docs, interface contracts, and applicable ADRs.
2. Identify the allowed scope, affected modules, existing behavior, and acceptance criteria.
3. Check `git status` and preserve unrelated user changes. Resolve material contract ambiguity before changing architecture or public interfaces.

## Implement and validate

4. Change only files needed for the task. Keep the domain independent from FastAPI, Next.js, and provider SDKs. Route external services through ports and adapters. Do not introduce a framework, package manager, database, or runtime outside the approved stack.
5. Run the smallest relevant checks, then the repository-wide checks required by the task. Foundation handoff requires `make check`, `make security-check`, and `make infra-test`; report any check that is not run as `NOT RUN` or `BLOCKED`.
6. Review the complete diff, including untracked files. Check for secrets, generated output, unnecessary lockfile changes, public contract changes, and scope creep.
7. Update documentation only where behavior or developer steps changed.
8. Deliver the changed files, validation commands and results, known limitations, and any required follow-up. Never report an unrun check as passing.

## Pull request contract

Use the repository PR template. Include the task ID, objective, summary, changed modules, contract effects, validation results, security effects, documentation, limitations, and scope deviations. Mark every check `PASS`, `FAIL`, `NOT RUN`, or `BLOCKED`. A PR is merge-ready only after all required checks pass and the acceptance criteria are satisfied.

## Repository boundaries

| Path | Responsibility |
| --- | --- |
| `apps/api` | Python/FastAPI backend and Python tests |
| `apps/web` | Next.js interface, BFF, and TypeScript tests |
| `infra` | Docker Compose infrastructure only |
| `scripts` | Developer commands and bounded tooling |
| `docs` | Architecture, contracts, ADRs, and operating guides |
| `.github` | Pull request metadata and CI with least privilege |

The application layer must not import TypeSafe or Qdrant SDKs directly. Domain code stays provider-independent. The TypeSafe SDK is backend-only. The frontend does not access Qdrant. The BFF does not forward arbitrary target URLs.

## Protected operations

Do not run `docker compose down -v`, delete a developer Qdrant volume, force-push, rewrite Git history, expose a secret in logs, or call the live Jev API without explicit authorization. Do not install project packages globally, skip quality gates while reporting success, alter an accepted ADR, or remove another contributor's uncommitted work. Dependency major upgrades and broad refactors require a separate task. Isolated test cleanup is allowed only for resources created by that test.
