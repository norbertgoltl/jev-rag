export type ErrorCode = "BACKEND_UNREACHABLE" | "BACKEND_TIMEOUT" | "BACKEND_INVALID_RESPONSE";
export class BackendError extends Error {
  constructor(public code: ErrorCode) {
    super(code);
  }
}
