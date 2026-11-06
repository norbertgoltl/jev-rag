# ADR-001 – Qdrant vector store

Status: accepted architecture decision. Related task: FND-004.

## Context

The project is a locally developed RAG system whose primary storage responsibility is semantic retrieval of document chunks and filtering by metadata. There is currently no existing PostgreSQL database or substantial relational business data model.

## Decision

The vector store is Qdrant, running as a separate Docker Compose service. Access is exclusively through an adapter implementing the backend's provider-independent VectorStorePort. The frontend and future agents do not receive direct database access.

## Alternatives considered

| Aspect | Qdrant | PostgreSQL + pgvector |
| --- | --- | --- |
| Base model | Dedicated vector search engine | Relational database with a vector extension |
| Filtering | Payload and payload indexes | SQL and relational indexes |
| Future hybrid retrieval | Dense/sparse combination | Vector and full-text combination |
| Business data and transactions | May require a separate authoritative database | Can be handled in the same relational database |
| Project implications | Directly fits the retrieval task | Would introduce relational infrastructure that is currently unused |

Qdrant is justified by the retrieval-focused scope and payload-based filtering. This is not a measured performance advantage over pgvector. PostgreSQL can be introduced later for authoritative storage of users, document lifecycles, job states, or conversations without replacing the vector index.

## Required operating conditions

| Area | Requirement | Implementation |
| --- | --- | --- |
| Execution | Docker Compose alongside the host-based API and web application | FND-015 |
| Network | HTTP binding `127.0.0.1:6333:6333`, no LAN exposure | FND-015 |
| Additional ports | gRPC and cluster ports are not published on the host | FND-015 |
| Image | Verified, specific version, not `latest` | FND-015 |
| Storage | Docker named volume at `/qdrant/storage` | FND-016 |
| Data retention | Restart and normal shutdown/startup preserve data, volume deletion is an explicit data-loss operation only | FND-016 |
| Readiness | Bounded connectivity check through the backend adapter, 503 when unavailable | FND-017 |
| Production | Authentication, TLS, network protection, snapshot and restore strategy | Separate task before production deployment |

The [Qdrant quickstart](https://qdrant.tech/documentation/quickstart/) warns that the default configuration has no authentication or encryption. A loopback binding is therefore mandatory. The local configuration alone is not a production deployment.

## Data management implications

Qdrant is a rebuildable search index. Original documents and processing configuration must be preserved separately. If documents are lost, their original content cannot be reliably recovered from the vector index alone.

The collection name, vector dimension, distance metric, and embedding model are RAG Core decisions. Foundation does not pre-create a business collection. Infrastructure persistence tests may use an isolated, synthetic test collection.

The RAG Core index design selects payload indexes based on actual filtering patterns, preferably before loading data, following the [Qdrant indexing guide](https://qdrant.tech/documentation/manage-data/indexing/). The future `access_scope` filter does not replace application-side authorization.

## Reconsideration

Revisit the decision if relational requirements become dominant, the operating cost of two stores becomes a problem, measured retrieval deficiencies emerge, or transactional consistency requires tighter integration. Technology preference alone is not a reason to migrate.

## Acceptance

FND-004 is complete: the choice, alternative, implications, and reconsideration conditions are recorded. Compose, volume, and connectivity test implementation belong to FND-015–017 and are not part of completing this ADR.

Related documents: [scope](../foundation/scope.md), [architecture](../architecture/system-architecture.md), [interfaces](../architecture/interface-contracts.md).
