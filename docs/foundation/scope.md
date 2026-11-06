# FND-001 – Foundation scope and requirements

Status: recorded decision. Completing this document does not mean that the entire Foundation implementation is complete.

## Goal

The project aims to provide a measurable RAG baseline handling Hungarian and English documents and questions. This requires a reproducible local development foundation with separate responsibilities for RAG, decisions, embeddings, and generation.

The initial implementation targets one developer, local execution, and a modular monolith. Module boundaries support the later addition of agents. A complete agent framework is not part of the baseline.

## Phases and scope

| Area | 01 Foundation | 02 RAG Core | Later phase |
| --- | --- | --- | --- |
| Repository, tooling | Monorepo, uv, pnpm, lockfiles, setup | Use existing tools | Extend as needed |
| Backend | FastAPI skeleton, configuration, health, error handling, request ID, logs | Ingestion and question-answering use cases | New business workflows |
| Frontend | Next.js skeleton and backend diagnostics | Document and question-answering interface | Additional user workflows |
| Qdrant | Compose, persistence, connectivity test, adapter boundary | Collection, upsert, search, delete, payload indexes | Optimize based on measured needs |
| Jev | Typed port, deterministic mock, SDK adapter, separate smoke test | Routing and relevance evaluation, measured policy | Additional decision use cases |
| Document processing | Chunk data requirements | Loading, chunking, reindexing | Additional formats |
| Embedding | Provider boundary and consistency requirements | Model selection and integration | Change models based on measured needs |
| Generative LLM | Responsibility and provider boundary | Model selection, source-grounded answers, citations | Additional capabilities |
| Evaluation | Ensure offline testability | Retrieval and answer quality, HU/EN measurements, insufficient evidence handling | Continuous regression measurement |
| Agent orchestration | Controlled extension point | No complete agent framework | Separately designed agentic phase |
| Production | Local security foundations | No production SLA | Scaling, multi-user authorization, TLS, backup, availability |

Classify new Epics as follows: development or execution foundations → Foundation, producing answers from documents or measuring their quality → RAG Core, autonomous tool use → agentic phase, production operations or multi-user functionality → production phase. Split mixed Epics along these boundaries.

## Foundation task groups

| Tasks | Output | Phase |
| --- | --- | --- |
| FND-001–004 | Scope, architecture, interface contracts, vector store ADR | 01 Foundation, design |
| FND-005–007 | Monorepo, Git configuration, developer commands | 01 Foundation, implementation |
| FND-008–011 | Python/uv, FastAPI, settings, HTTP contract implementation, logging | 01 Foundation, implementation |
| FND-012–014 | Next.js, typed backend client, diagnostics interface | 01 Foundation, implementation |
| FND-015–017 | Qdrant Compose, persistence, real readiness probe | 01 Foundation, implementation |
| FND-018–020 | DecisionPort, mock, TypeSafe SDK adapter, and contract/smoke tests | 01 Foundation, implementation |
| FND-021–023 | Backend/frontend quality checks and CI | 01 Foundation, implementation |
| FND-024–026 | Security and agent development rules, integrated release gate | 01 Foundation, validation |

FND-003 provides concrete contracts for later implementation. Running endpoints and adapters are not delivered as part of FND-001–004.

## Non-functional requirements

| Requirement | Verifiable expectation at the end of Foundation |
| --- | --- |
| Isolation | FastAPI in a uv environment and Next.js with pnpm on the host, infrastructure in Docker, no global project dependencies |
| Reproducibility | Pinned runtime and package versions, uv/pnpm lockfiles, specific Qdrant image tag, documented clean setup |
| Testability | Unit and simulated integration tests run without an AI API key or external AI API, Docker and live smoke can be run separately |
| Security | Secrets remain server-only and outside version control, infrastructure uses loopback bindings, sanitized errors and logs |
| Observability | Structured logs, per-request request ID, separate liveness and Qdrant readiness |
| Extensibility | SDK-independent domain/port layer, SDKs confined to adapters, policy in the application layer |
| Quality | Automated lint, typecheck, tests, and CI, a failed check must not report success |

## Acceptance and related decisions

FND-001 is complete: phase boundaries and the classification of all known Foundation task groups are recorded. Working capabilities in the other phases require separate implementation and test evidence.

- [System architecture](../architecture/system-architecture.md)
- [Interface contracts](../architecture/interface-contracts.md)
- [ADR-001: Qdrant](../adr/ADR-001-vector-store.md)
