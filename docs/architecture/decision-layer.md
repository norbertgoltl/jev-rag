# Decision Layer

The Decision Layer provides structured decisions and does not execute application-level operations. It does not generate natural-language answers, invoke tools, or contain RAG routing, ranking, or execution thresholds.

The application layer uses the asynchronous `DecisionPort.evaluate(DecisionRequest) -> DecisionResult` port. The domain and application layers do not import the TypeSafe SDK. Exceptions belong to the `DecisionError` hierarchy, with a safe code and retryable flag. The provider selects mock/live/disabled adapters based on configuration. Errors do not trigger an automatic live → mock switch.

## Contracts

The request contains a non-null text or JSON object/array state and a non-empty question-ID map. Identifiers are non-empty, and the primitive discriminator is required. Non-finite JSON numbers are rejected.

- Choice: non-empty instructions, at least two options, and optional text descriptions. Returns a choice, per-option probabilities, and confidence.
- Score: 2–10 ordered, non-empty text levels. The first level has index 0. Returns a score preserving fractional values, an integer-indexed distribution, and confidence.
- Noul: non-empty instructions and optional true/false text criteria. The noul value is itself a probability, with no additional confidence.

The result answers exactly the requested question IDs using the same primitives. The Choice selection and distribution keys belong to the supplied options. The Score and distribution indexes are within the supplied scale. Every probability/confidence value is finite and between 0 and 1. Invalid or missing results are not completed with default decisions. The model, optional provider request ID, and token usage are preserved. Numeric values are not rounded, and confidence does not imply execution permission.

## Adapters

MockDecisionAdapter uses explicit fixtures keyed by the complete request. It uses no network, randomness, or automatic answer generation. The same request and fixture produce the same result. Missing or invalid fixtures raise DecisionInvalidResponseError. Tests may also configure domain errors. Synthetic probability and confidence values do not measure Jev accuracy.

TypeSafeDecisionAdapter uses the official `typesafe-sdk==0.7.5` AsyncTypeSafeClient. One evaluate call sends multiple named questions in a single system_one call. The mapper uses the SDK Choice/Score/Noul types, then revalidates the SystemOneResponse result against the internal request. An unknown primitive omitted by the SDK must be rejected as a missing answer.

The client is created once per worker process during the FastAPI lifespan and closed asynchronously at shutdown. DecisionPort is available through a FastAPI dependency provider and can be overridden in tests. The real SDK client is not initialized in mock/disabled mode. Qdrant readiness and decision capability are independent. No public Jev HTTP endpoint has been added.
