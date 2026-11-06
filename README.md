# Jev + RAG

[![CI](https://github.com/norbertgoltl/jev-rag/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/norbertgoltl/jev-rag/actions/workflows/ci.yml)

A document-grounded question-answering system that combines Retrieval-Augmented Generation (RAG) with the Jev decision layer. The system answers questions from loaded documents and makes the sources of each answer identifiable. It supports Hungarian and English questions and a mixed-language document collection.

## Status

The **01 Foundation** phase is accepted. It provides a FastAPI backend, a Next.js BFF with a diagnostics page, Qdrant infrastructure, and a typed Jev DecisionPort adapter. The RAG features themselves (ingestion, retrieval, answer generation, evaluation) belong to the planned **02 RAG Core** phase and are not implemented yet.

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

The task groups are defined in the [scope document](docs/foundation/scope.md). Evidence, test results, and the one standing acceptance condition are in the [release report](docs/foundation/release-report.md). The acceptance criteria are in the [release checklist](docs/foundation/release-checklist.md).

## Planned RAG Core flow

1. **Ingestion:** load, process, chunk, and index documents for search.
2. **Retrieval:** retrieve document chunks relevant to the user's question.
3. **Jev decision layer:** support answer processing based on the retrieved evidence.
4. **Answer generation:** produce an answer grounded in the available sources, with citations.
5. **Evaluation:** measure retrieval and answer quality, including answers with insufficient supporting evidence.

## Tech stack

| Area | Technology |
| --- | --- |
| Backend | Python 3.14.8, `uv`, FastAPI, Pydantic, Ruff, strict mypy, pytest |
| Frontend | Node.js 24.22.1, pnpm 12.15.0, Next.js 16.4.2, TypeScript, ESLint, Prettier, Vitest |
| Vector store | Qdrant (version-pinned image) in Docker Compose, see [ADR-001](docs/adr/ADR-001-vector-store.md) |
| Decision provider | TypeSafe SDK, only through the backend `DecisionPort` adapter |

The applications run on the host. Docker runs only the infrastructure. The primary development environment is macOS Apple Silicon.

## Repository layout

| Path | Responsibility |
| --- | --- |
| `apps/api` | Python/FastAPI application with its own `uv.lock` |
| `apps/web` | Next.js UI and BFF in the root pnpm workspace (`pnpm-lock.yaml`) |
| `infra` | Docker Compose infrastructure |
| `scripts` | Developer commands and bounded validation tooling |
| `docs` | Architecture, contracts, ADRs, and guides |
| `.github` | CI workflow and pull request template |

## Getting started

### Prerequisites

- Docker Desktop, started by you. The project never changes Docker Desktop settings or contexts.
- Git, Make, `uv`, `fnm`, and pnpm 12.15.0. The pinned Python and Node.js versions come from `apps/api/.python-version` and `.node-version`.

Details: [macOS setup](docs/development/macos-setup.md).

### Install

```sh
fnm use
cp .env.example .env
make doctor
make setup
```

`.env.example` selects mock Jev mode and has no credentials, so no API key is needed. If you already have an `.env`, keep it and do not copy over it. `make doctor` only checks tools and versions.

### Run

```sh
make up
make dev-api
```

Start the frontend in a second terminal:

```sh
make dev-web
```

The interface is at `http://127.0.0.1:3000` and the backend at `http://127.0.0.1:8000`. Qdrant listens on `http://127.0.0.1:6333`. Check readiness and stop the infrastructure with:

```sh
make health
make down
```

`make down` keeps the Qdrant data volume. If something does not start, see [troubleshooting](docs/development/troubleshooting.md).

## Development

Run `make help` for all commands. The most used ones:

| Command | Purpose |
| --- | --- |
| `make check` | Full offline gate: lint, format check, types, tests with coverage, and frontend build |
| `make test` | Backend and frontend tests |
| `make lint`, `make typecheck` | Lint and type checks for both applications |
| `make format`, `make format-frontend` | Format backend or frontend sources |
| `make security-check`, `make security-smoke` | Secret scan, boundary checks, and negative security cases |
| `make infra-test` | Isolated Qdrant lifecycle acceptance test |
| `make jev-smoke` | Live Jev request, separately authorized and paid |

`make check` and the security checks run offline and need no API key. Details: [development environment and Git workflow](docs/development/workflow.md), [testing](docs/development/testing.md), and [CI](docs/development/ci.md).

## Documentation

| Topic | Documents |
| --- | --- |
| Architecture | [System architecture](docs/architecture/system-architecture.md), [decision layer](docs/architecture/decision-layer.md), [ADR-001: Qdrant](docs/adr/ADR-001-vector-store.md) |
| Interfaces | [Interface contracts](docs/architecture/interface-contracts.md), [OpenAPI contract](docs/architecture/contracts/foundation.openapi.json) |
| Applications | [API](apps/api/README.md), [frontend](apps/web/README.md), [backend guide](docs/development/backend.md), [infrastructure](docs/development/infrastructure.md), [Jev integration](docs/development/jev-integration.md) |
| Operations | [Troubleshooting](docs/development/troubleshooting.md), [security baseline](docs/development/security.md) |
| Release | [Scope](docs/foundation/scope.md), [release checklist](docs/foundation/release-checklist.md), [release report](docs/foundation/release-report.md) |

## Security

`TYPESAFE_API_KEY` is used only in the backend process and must never enter the frontend bundle, logs, or public error responses. Security rules, the secret incident procedure, and the Gitleaks checks are in the [security baseline](docs/development/security.md).

## Contributing

Changes go through pull requests that use the [pull request template](.github/pull_request_template.md). A pull request is ready to merge when its acceptance criteria and the required CI checks pass. The workflow is described in [development environment and Git workflow](docs/development/workflow.md). Repository rules for agents and contributors are in [AGENTS.md](AGENTS.md) and the [agent workflow](docs/development/agent-workflow.md).
