# Jev SDK integration

The asynchronous DecisionPort isolates application code from typesafe-sdk 0.7.5. Choice, Score and Noul responses are normalized and validated against exact question IDs and configured options/scales. There is no new public endpoint or RAG workflow.

JEV_MODE selects mock, live or disabled. Development defaults to mock; production requires explicit live or disabled. Live requires a server-side TYPESAFE_API_KEY. The pinned model is jev-1.13.0, timeout 5s, retry max 1 and retry budget 10s. SDK retry handles transient errors and Retry-After; there is no application retry loop or live-to-mock fallback. The FastAPI lifespan owns one reusable client and closes it on shutdown. get_decision_port supports dependency overrides.

Logs include safe metadata only. SDK body/debug logs are suppressed and warnings sanitized. The decision layer never executes application actions. Qdrant readiness remains independent.

Run make test-api for offline tests. SDK transport tests use MockTransport, with zero-delay retry configuration. Live smoke and the expanded contract test suite are introduced in FND-020.
