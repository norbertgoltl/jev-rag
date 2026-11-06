# FND-003 – Interfaces and API contracts

Status: specified contracts. The machine-readable HTTP contract is [foundation.openapi.json](contracts/foundation.openapi.json), OpenAPI 3.1.0.

This is the contract-first foundation for later implementation. The HTTP schemas are already concrete here. Running FastAPI endpoints belong to FND-009–011, the Qdrant adapter to FND-017, and DecisionPort and its adapters to FND-018–020. Embedding and generator implementations are not part of Foundation.

## HTTP API

All business endpoints use the `/api/v1` prefix. Process diagnostic health endpoints remain outside it. Successful responses are endpoint-specific, without a general response wrapper.

| Method and path | HTTP | Exact JSON response |
| --- | --- | --- |
| `GET /health/live` | 200 | `{"status":"alive"}` |
| `GET /health/ready` | 200 | `{"status":"ready","dependencies":{"qdrant":"up"}}` |
| `GET /health/ready` | 503 | `{"status":"not_ready","dependencies":{"qdrant":"down"}}` |
| `GET /api/v1/system/status` | 200 | `{"service":"api","status":"ok"}` |

Liveness and system status do not call external services. Status indicates API availability and does not replace readiness. Readiness checks the required Qdrant connection with a configured, finite timeout. The initial probe without a real adapter reports `down` and must not report a false `ready` state. Jev availability is not a readiness condition.

An expected readiness dependency failure uses the diagnostic 503 response in the table, not the general error envelope. Unexpected application errors on any endpoint use the shared 500 error schema. Responses contain no credentials, internal addresses, connection strings, or stack traces.

FND-009 will also provide the `/openapi.json` and `/docs` developer interfaces. The OpenAPI file stored here is the contract for the three Foundation endpoints, not an export from a running application.

## Errors and request ID

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request",
    "details": [{"field": "body.question", "code": "required"}]
  },
  "request_id": "80d3c0b6-9b52-4aa9-85a0-5a657bb402d8"
}
```

| Field | Type and condition |
| --- | --- |
| `error.code` | Required, non-empty stable machine code |
| `error.message` | Required, safe, non-empty public message |
| `error.details` | Required key, `null` or a list of sanitized `{field, code}` items |
| `request_id` | Required identifier matching the response `X-Request-ID` header |

The optional details in the initial plan are refined into a consistently present, nullable `details` field. Validation data may contain only safe field identifiers and error codes, never input values or raw exceptions.

| Case | HTTP | `error.code` | Public message |
| --- | --- | --- | --- |
| Invalid request | 422 | `VALIDATION_ERROR` | `Invalid request` |
| Unknown endpoint | 404 | `NOT_FOUND` | `Resource not found` |
| Disallowed HTTP method | 405 | `METHOD_NOT_ALLOWED` | `Method not allowed` |
| Future business dependency failure | 503 | `SERVICE_UNAVAILABLE` | `Service unavailable` |
| Unhandled error | 500 | `INTERNAL_ERROR` | `Internal server error` |

The 405 response preserves the `Allow` header. Foundation diagnostic GET endpoints accept no business input, so the 422 schema is a shared component for future endpoints, not an invented request parameter.

Every response, including health and error responses, contains an `X-Request-ID` header. An incoming identifier may contain 1–64 ASCII letters, digits, `.`, `_`, or `-` characters. Missing or invalid values are replaced by a generated UUID4. An invalid header does not cause a 422. Request contexts must not leak between asynchronous requests.

## Internal ports

Ports use their own domain models. They must not return SDK response objects or SDK exceptions to the application layer. The signatures below are implementation contracts. The relevant backend task introduces the referenced types.

```python
class DecisionPort(Protocol):
    async def evaluate(self, request: DecisionRequest) -> DecisionResult: ...


class VectorStorePort(Protocol):
    async def check_health(self) -> bool: ...
```

`VectorStorePort.check_health` does not write data or create collections. It returns `True` on success and `False` on timeout or known connectivity errors. Readiness uses only this provider-independent result. The adapter safely logs technical errors. The timeout is configurable and finite. The real probe calls Qdrant and can be replaced by a fake in unit tests.

| Future boundary | Input | Result and invariant |
| --- | --- | --- |
| Vector upsert | Versioned chunks, model identifier, vectors with the correct dimension | Idempotent indexing by stable chunk identifier |
| Vector search | Query vector, model identifier, limit, application-verified scope and filters | Ranked chunks and numeric retrieval score, without SDK types |
| Vector delete | Explicit document/chunk identifier and version boundary | Delete only the selected data |
| EmbeddingPort | Document texts or query, selected model configuration | Finite-valued vectors, model identifier and dimension, invalid model/dimension rejected |
| GeneratorPort | Question and identifiable source texts | Answer and identifiers of sources used, without SDK types |

These are requirement boundaries, not methods or empty implementations to create in advance. RAG Core defines the final types, collection schema, embedding dimension, and retrieval score semantics. Generation does not perform retrieval directly. The application coordinates source selection.

## Jev Decision Contract

| Property | Contract |
| --- | --- |
| SDK and client | `typesafe-sdk`, `AsyncTypeSafeClient`, from the backend |
| Operation | `system_one(state=..., questions=...)`, from the adapter |
| Configuration | Server-side `TYPESAFE_API_KEY`, explicit, configurable model identifier |
| Modes | Default offline mock, separate explicit live mode, no calls when disabled |
| Lifecycle | Client reused per worker, asynchronous shutdown |
| Resilience | 5 s HTTP timeout, at most 1 SDK retry, 10 s retry budget, no second retry loop |
| Fallback | Explicit use case decision, no automatic live → mock switch |

The [asynchronous client](https://docs.typesafe.ai/sdk/python/api/clients/async) supports timeouts and retry policies. The exact SDK version, model pin, and completed compatibility checks are outputs of FND-019–020. A model change must pass contract tests and, for future business policy, quality measurements as well.

### Input

`DecisionRequest.state`: non-null string, JSON object, or JSON array. `questions`: a map of at least one question, keyed by non-empty, unique string identifiers. `QuestionSpec`: a union discriminated by `type`.

| Type | Fields |
| --- | --- |
| `ChoiceQuestionSpec` | `type="choice"`, non-empty `instructions`, `criteria`: a map from at least two non-empty option identifiers to strings or null |
| `ScoreQuestionSpec` | `type="score"`, non-empty `instructions`, `criteria`: 2–10 ordered, non-empty text levels |
| `NoulQuestionSpec` | `type="noul"`, non-empty `instructions`, optional `criteria`: text descriptions for `true` and/or `false` |

Foundation uses text criteria. Additional multimodal and structured question capabilities in the SDK are not automatically exposed through the internal port. The adapter maps provider types according to the [TypeSafe question contract](https://docs.typesafe.ai/sdk/python/api/types/questions).

### Output and validation

`DecisionResult`: required, non-empty `model` and `answers` map, optionally nullable `provider_request_id`, non-negative integer `input_tokens` and `output_tokens`. `answers` contains exactly one answer for every requested identifier, with no extras.

| Answer type | Fields and meaning |
| --- | --- |
| `ChoiceAnswer` | `type="choice"`, allowed `choice`, `probabilities` keyed by option identifier, `confidence` |
| `ScoreAnswer` | `type="score"`, `score` preserving fractional values, `probabilities` keyed by level index, `confidence` |
| `NoulAnswer` | `type="noul"`, `noul`: probability between 0 and 1, no separate confidence |

The Score range is `0..len(criteria)-1`. Probabilities and confidence are finite numbers between 0 and 1. Choice distribution keys are exactly the options. Score distribution keys are the integer indexes of the scale. The returned primitive matches the requested one. Answers must not be rounded to integer scores, and missing fields must not be filled with invented values. The adapter converts [SDK responses](https://docs.typesafe.ai/sdk/python/api/types/responses) into its own domain model, preserving the actual model identifier.

### Errors, mock, and execution boundary

For known provider errors, `evaluate` may raise only a `DecisionError` subclass. Expected categories: `DecisionInvalidRequestError`, `DecisionAuthenticationError`, `DecisionRateLimitedError`, `DecisionUnavailableError`, `DecisionTimeoutError`, `DecisionInvalidResponseError`, `DecisionConfigurationError`. Invalid or incomplete provider results are invalid responses, not successful decisions.

400/401/403/422 errors are not retried. 429, transient provider errors, and network errors may be retried within bounds. Errors must not contain API keys, state, or raw provider bodies. SDK DEBUG body logging is not allowed.

The mock returns configured fixtures deterministically, without external network access or an API key. A missing fixture is an explicit error. The same input and output invariants apply as for the live adapter. Normal tests run offline. Live smoke runs separately with synthetic HU/EN input and checks structure rather than a specific model judgment.

The model response is decision input. The application executes, rejects, or selects an explicit fallback according to deterministic policy. Numeric calculations, date comparisons, and authorization are implemented in code and do not rely on model judgment.

## RAG chunk data requirements

| Field | Requirement |
| --- | --- |
| `chunk_id` | Stable identifier for the given chunk version |
| `document_id` | Source document identifier |
| `document_version` | Version of the processed source |
| `content` | Searchable text |
| `source_uri` | Citable source location |
| `chunk_index` | Non-negative position within the document |
| `metadata` | Structured, JSON-compatible search metadata |
| `embedding_model` | Identifier of the model that produced the vector |
| `access_scope` | Application-verified authorization scope |

Specific field types and identifier generation, model, dimension, and collection schema are RAG Core decisions. The document version and processing configuration together make the index reproducible. The application determines and verifies the search scope. It must not accept an arbitrary scope from the user.

## Acceptance checks for implementation tasks

| Check | Expected result | Owner |
| --- | --- | --- |
| HTTP contract | Exact endpoint, status code, JSON, and request ID | FND-009–011 |
| Health isolation | Liveness/status without external calls, Qdrant down → 503, unaffected by Jev down | FND-009, FND-017 |
| Error content | Consistent envelope, sanitized details, no secrets or stack traces | FND-011 |
| Qdrant boundary | Fake probe in unit tests, real probe in separate integration tests | FND-017 |
| Decision contract | All three primitives, exact identifier matching, invalid input/output rejected | FND-018–020 |
| Provider errors | Bounded timeout/retry, no SDK error leakage, no silent fallback | FND-019–020 |
| Offline execution | Mock and SDK contract tests without external AI calls, separate live smoke | FND-020–023 |

FND-003 specification acceptance is complete: API versioning, errors, health, DecisionPort, the Qdrant boundary, and future provider boundaries are defined. The runtime checks above are completion conditions for the designated implementation tasks.
