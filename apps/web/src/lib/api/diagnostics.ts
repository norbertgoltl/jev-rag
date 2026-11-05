import "server-only";
import { BACKEND_PATHS, backendGet } from "./backend-client";
import { type Diagnostics, QDRANT_BY_READINESS, isStatus, readiness } from "./contracts";
import { BackendError, type ErrorCode } from "./errors";

type DiagnosticsResult = { status: number; body: Diagnostics };

const HTTP_STATUS_BY_ERROR: Record<ErrorCode, number> = {
  BACKEND_TIMEOUT: 504,
  BACKEND_UNREACHABLE: 503,
  BACKEND_INVALID_RESPONSE: 502,
};

function offline(requestId: string, code: ErrorCode): DiagnosticsResult {
  return {
    status: HTTP_STATUS_BY_ERROR[code],
    body: {
      backend: "offline",
      readiness: "unknown",
      qdrant: "unknown",
      request_id: requestId,
      error: { code, message: "Backend service unavailable" },
    },
  };
}

function online(requestId: string, state: ReturnType<typeof readiness>): DiagnosticsResult {
  return {
    status: 200,
    body: {
      backend: "online",
      readiness: state,
      qdrant: QDRANT_BY_READINESS[state],
      request_id: requestId,
    },
  };
}

function errorCodeOf(system: PromiseSettledResult<{ status: number; body: unknown }>): ErrorCode {
  if (system.status === "rejected" && system.reason instanceof BackendError) {
    return system.reason.code;
  }
  return "BACKEND_INVALID_RESPONSE";
}

export async function diagnose(requestId: string): Promise<DiagnosticsResult> {
  const [system, ready] = await Promise.allSettled([
    backendGet(BACKEND_PATHS.systemStatus, requestId),
    backendGet(BACKEND_PATHS.readiness, requestId),
  ]);
  const systemIsOk =
    system.status === "fulfilled" && system.value.status === 200 && isStatus(system.value.body);
  if (!systemIsOk) return offline(requestId, errorCodeOf(system));

  const state =
    ready.status === "fulfilled" ? readiness(ready.value.body, ready.value.status) : "unknown";
  return online(requestId, state);
}
