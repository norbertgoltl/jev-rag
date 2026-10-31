# Repository agent instructions

## 1. Project context

Jev + RAG is a document-grounded question-answering project. The current Foundation provides the Python/FastAPI API, Next.js BFF and diagnostics, Qdrant infrastructure, and a typed Jev DecisionPort. Do not implement future RAG ingestion, retrieval, generation, or agent orchestration unless the task explicitly requests it.

## 2. Source of truth

- Scope and phases: [`docs/foundation/scope.md`](docs/foundation/scope.md).
- Architecture: [`docs/architecture/system-architecture.md`](docs/architecture/system-architecture.md) and [`docs/architecture/decision-layer.md`](docs/architecture/decision-layer.md).
- Interfaces: [`docs/architecture/interface-contracts.md`](docs/architecture/interface-contracts.md) and [`docs/architecture/contracts/foundation.openapi.json`](docs/architecture/contracts/foundation.openapi.json).
- Accepted decision: [`docs/adr/ADR-001-vector-store.md`](docs/adr/ADR-001-vector-store.md).
- Security and workflow: [`docs/development/security.md`](docs/development/security.md), [`docs/development/agent-workflow.md`](docs/development/agent-workflow.md).
- When a directory contains another `AGENTS.md`, follow both; the more specific instructions apply to that directory.

## 3. Repository structure

| Path | Responsibility |
| --- | --- |
| `apps/api` | Python/FastAPI application and tests |
| `apps/web` | Next.js UI, BFF, and TypeScript tests |
| `infra` | Docker Compose infrastructure |
| `scripts` | Developer CLI and bounded validation tooling |
| `docs` | Architecture, contracts, ADRs, and guides |
| `.github` | CI and pull request metadata |

## 4. Technology stack

- Backend: Python 3.14.8, `uv`, FastAPI, Pydantic, Ruff, strict mypy, pytest.
- Frontend: Node.js 24.22.1, pnpm 12.15.0, Next.js 16.4.2, TypeScript, ESLint, Vitest.
- Generate a Next.js app only with the approved `create-next-app@16.4.2`.
- Infrastructure: Docker Desktop and Docker Compose V2; Qdrant image is version-pinned.
- Decision provider: TypeSafe SDK only through the backend `DecisionPort` adapter.
- Keep `apps/api/uv.lock` and root `pnpm-lock.yaml` authoritative. Do not add global project dependencies.

## 5. Architecture rules

- Keep domain types independent from FastAPI, Next.js, Qdrant, and TypeSafe SDKs.
- Application code depends on domain types and ports; adapters implement external integrations.
- Only the backend adapter may construct or call the TypeSafe SDK.
- The browser calls the Next.js BFF. The BFF uses a server-only backend URL and never proxies arbitrary URLs.
- The frontend must not import backend Python modules or contact Qdrant directly.
- Keep Docker infrastructure limited to infrastructure services; applications run on the host.
- Treat model output as input to deterministic application policy, never as authorization.

## 6. Development environment

Use the pinned Python, Node.js, and pnpm versions above. Docker Desktop must be started by the developer; project commands must not change global Docker contexts or Desktop settings. Follow [`docs/development/workflow.md`](docs/development/workflow.md) and [`docs/development/macos-setup.md`](docs/development/macos-setup.md) when present. Do not overwrite an existing `.env`.

## 7. Implementation workflow

1. Read the task, this file, scoped agent instructions, relevant ADRs, contracts, and current implementation.
2. Check `git status` and preserve unrelated edits. Identify scope and acceptance criteria.
3. Make the smallest coherent change within the requested boundaries. Resolve blocking contract ambiguity before changing accepted architecture.
4. Run relevant validation and the checks required by the task. Record actual outcomes.
5. Review tracked and untracked diffs for secrets, generated files, unrelated changes, and unnecessary lockfile updates.
6. Update affected documentation and report files, changed paths, verification, limitations, and follow-up actions.

## 8. Coding standards

- Write code identifiers, comments, docstrings, tests, configuration messages, and developer-facing CLI text in English.
- Python must pass Ruff, formatting, strict mypy, and pytest. Keep tests deterministic and offline by default.
- TypeScript must pass ESLint with zero warnings, typecheck, Vitest coverage, and production build.
- Keep public HTTP contracts and generated files aligned with their source of truth.
- Add dependencies only when required by the task; update the corresponding lockfile intentionally.

## 9. Security rules

- Never commit real `.env` files, credentials, private keys, or provider responses containing secrets.
- Keep `TYPESAFE_API_KEY` backend-only. Do not place it in frontend source, `NEXT_PUBLIC_*`, `next.config.*` `env`, browser output, logs, or public errors.
- Do not log authorization headers, raw request bodies, private provider responses, or tracebacks in public errors.
- Keep Qdrant bound to `127.0.0.1`, version-pinned, non-privileged, and without Docker socket mounts.
- Run `make security-check` and `make security-smoke` for security-sensitive changes.
- See [`docs/development/security.md`](docs/development/security.md) for incident handling and scanner use.

## 10. Validation

Run the applicable component checks; the full offline application gate is `make check`. Security validation is `make security-setup`, `make security-check`, and `make security-smoke`. Infrastructure lifecycle changes require `make infra-test`. `make doctor` checks local prerequisites. The live Jev smoke is separate and requires explicit authorization. Report unrun checks as `NOT RUN` or `BLOCKED`, never as passing.

## 11. Pull request contract

Use [`.github/pull_request_template.md`](.github/pull_request_template.md). Include task ID, summary, changed files, contract effects, validation commands and statuses, security effects, documentation, limitations, and scope deviations. A change is merge-ready only when acceptance criteria and required CI checks pass.

## 12. Prohibited operations

- Never run `docker compose down -v`, delete an existing developer volume, or reset Docker Desktop as routine cleanup.
- Never force-push or rewrite Git history without explicit authorization.
- Never expose a secret in output, logs, test reports, or pull request text.
- Never call the live Jev API without explicit authorization.
- Never install project dependencies globally or disable a quality gate to make CI green.
- Do not make dependency major upgrades, accepted ADR changes, broad unrelated refactors, or remove another contributor's uncommitted work as part of an unrelated task.
- Isolated test cleanup may remove only resources created and identified by that test.
