# Jev + RAG

## Description

**Jev + RAG** is a planned document-grounded question-answering system that combines Retrieval-Augmented Generation (RAG) with the Jev decision layer.

The **01 Foundation** phase provides a working FastAPI backend, Next.js BFF, Qdrant infrastructure, and Jev DecisionPort adapter. The **02 RAG Core** phase builds a working, measurable RAG baseline on this foundation.

## Foundation status

The 01 Foundation phase is accepted. All 26 tasks are done and validated:

| Tasks | Delivered | Status |
| --- | --- | --- |
| FND-001–004 | Scope, system architecture, interface contracts with the OpenAPI contract, vector store ADR | Done |
| FND-005–007 | Monorepo structure, Git configuration, developer commands (`make`) | Done |
| FND-008–011 | FastAPI backend: settings, health endpoints, error handling, request IDs, structured logging | Done |
| FND-012–014 | Next.js frontend: BFF, typed backend client, diagnostics page | Done |
| FND-015–017 | Qdrant with Docker Compose, persistence, real readiness probe | Done |
| FND-018–020 | Jev DecisionPort, deterministic mock, TypeSafe SDK adapter, contract and smoke tests | Done |
| FND-021–023 | Backend and frontend quality checks and CI | Done |
| FND-024–026 | Security baseline, agent workflow rules, integrated release gate | Done |

The task groups are defined in the [scope document](docs/foundation/scope.md). Evidence, test results, and the one standing acceptance condition are recorded in the [release report](docs/foundation/release-report.md), and the acceptance criteria are in the [release checklist](docs/foundation/release-checklist.md).

## Project goal

The system aims to answer user questions using information retrieved from loaded documents and make the sources used for each answer identifiable.

The design supports Hungarian and English questions and a document collection containing both languages. Key considerations include evaluating retrieval and answer quality and handling answers with insufficient supporting evidence.

## Planned minimum functionality

The planned processing flow for **02 RAG Core**:

1. **Ingestion:** load, process, chunk, and index documents for search.
2. **Retrieval:** retrieve document chunks relevant to the user's question.
3. **Jev Decision Layer:** support subsequent answer processing based on the retrieved evidence.
4. **Answer Generation:** produce an answer grounded in the available sources, with source citations.
5. **Evaluation:** assess retrieval and answer quality in a verifiable way.

The backend uses Python/FastAPI, with `uv` managing the local Python development environment. The web interface uses Next.js. The primary supported development environment is macOS Apple Silicon, with Qdrant running in Docker Compose.

The RAG capabilities listed above are **planned features** and are not part of the current Foundation.

## Foundation architecture decisions

- [Scope and requirements](docs/foundation/scope.md)
- [System architecture](docs/architecture/system-architecture.md)
- [Interfaces and API contracts](docs/architecture/interface-contracts.md)
- [Machine-readable OpenAPI contract](docs/architecture/contracts/foundation.openapi.json)
- [Qdrant vector store ADR](docs/adr/ADR-001-vector-store.md)

The decision specifies a modular FastAPI backend, Next.js frontend, separate Jev decision adapter, and Qdrant running in Docker Compose.

## Monorepo and development environment

The primary environment is macOS Apple Silicon, POSIX shell, and GNU/BSD Make. The pinned Node.js version is `24.22.1`, and the pnpm version is `12.15.0`. The backend uses uv-managed Python `3.14.8`.

| Directory | Responsibility |
| --- | --- |
| `apps/api` | Python/FastAPI project with its own uv.lock and .venv |
| `apps/web` | Next.js project in the root pnpm workspace |
| `infra/compose.yaml` | Docker infrastructure |
| `scripts` | Developer commands and smoke tests |
| `docs` | Architecture, ADRs, and development guides |
| `.github` | PR template and GitHub Actions CI |

Run from the repository root:

```sh
make help
make doctor
make smoke
```

`doctor` only performs checks and exits with an error when a tool is missing or a version differs. `smoke` checks the CLI offline using simulated tools.

## Local quickstart

Docker Desktop must be running. The pinned Python, Node.js, and pnpm versions are documented in [`docs/development/macos-setup.md`](docs/development/macos-setup.md).

```sh
fnm use
cp .env.example .env
make doctor
make setup
make up
```

Start in separate terminals:

```sh
make dev-api
make dev-web
```

The interface is available at `http://127.0.0.1:3000`, and the backend at `http://127.0.0.1:8000`. `.env.example` uses mock Jev mode, so initial setup does not require a live API key. Check readiness and stop the infrastructure:

```sh
make health
make down
```

`make down` preserves the Qdrant data volume.

Backend details: [API README](apps/api/README.md).

The Python project root is `apps/api`, and the pnpm workspace root is the repository. The API lockfile is `apps/api/uv.lock`, and the frontend uses the single root `pnpm-lock.yaml`. FastAPI and Next.js run on the host, with only infrastructure running in Docker.

Details: [development environment, commands, and Git workflow](docs/development/workflow.md).

Available backend commands are `make setup-api`, `make dev-api`, and `make test-api`. They use the locked `apps/api/uv.lock`.

Start the frontend with `make dev-web`. Installation, API communication, and checks: [frontend documentation](apps/web/README.md).

Qdrant infrastructure: `make up`, `make health`, `make status`, `make down`. Prerequisites, named volume, and isolated tests: [infrastructure](docs/development/infrastructure.md).

Quality gate: `make check`. Testing and CI guides: [testing](docs/development/testing.md), [CI](docs/development/ci.md). Configuration and separately authorized live smoke: [Jev integration](docs/development/jev-integration.md).

## Security and agent workflow

`TYPESAFE_API_KEY` may only be used in the backend process and must never enter the frontend bundle or public error responses. Security rules, the secret incident procedure, and Gitleaks checks are documented in the [security baseline](docs/development/security.md). [AGENTS.md](AGENTS.md) and the [agent workflow](docs/development/agent-workflow.md) define repository rules for agents and pull requests.

The local quality gate is `make check`. Integrated handoff additionally requires `make security-check`, `make security-smoke`, and `make infra-test`. Mark results as PASS in the [release report](docs/foundation/release-report.md) only after actually running the checks.
