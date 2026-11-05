import "server-only";
import { getConfig } from "../config/server";
import { BackendError } from "./errors";

/** Backend endpoints the BFF may call; defined by docs/architecture/contracts/foundation.openapi.json. */
export const BACKEND_PATHS = {
  systemStatus: "/api/v1/system/status",
  readiness: "/health/ready",
} as const;

export type BackendPath = (typeof BACKEND_PATHS)[keyof typeof BACKEND_PATHS];

export async function backendGet(path: BackendPath, requestId: string) {
  const config = getConfig();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), config.timeout);
  try {
    const response = await fetch(config.url + path, {
      method: "GET",
      cache: "no-store",
      headers: { "X-Request-ID": requestId },
      signal: controller.signal,
      redirect: "error",
    });
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      if (controller.signal.aborted) throw new BackendError("BACKEND_TIMEOUT");
      throw new BackendError("BACKEND_INVALID_RESPONSE");
    }
    return { status: response.status, body };
  } catch (error) {
    if (error instanceof BackendError) throw error;
    throw new BackendError(controller.signal.aborted ? "BACKEND_TIMEOUT" : "BACKEND_UNREACHABLE");
  } finally {
    clearTimeout(timer);
  }
}
