export type Readiness = "ready" | "not_ready" | "unknown";
export type QdrantState = "up" | "down" | "unknown";

export type Diagnostics = {
  backend: "online" | "offline";
  readiness: Readiness;
  qdrant: QdrantState;
  request_id: string;
  error?: { code: string; message: string };
};

/** Qdrant state implied by each readiness value; the only combinations the BFF emits. */
export const QDRANT_BY_READINESS: Record<Readiness, QdrantState> = {
  ready: "up",
  not_ready: "down",
  unknown: "unknown",
};

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null;
}

/** Accepts the `GET /api/v1/system/status` response defined by the OpenAPI contract. */
export function isStatus(value: unknown): boolean {
  return isRecord(value) && value.service === "api" && value.status === "ok";
}

/** Maps a `GET /health/ready` response (HTTP status and body) to a readiness value. */
export function readiness(value: unknown, httpStatus: number): Readiness {
  if (!isRecord(value) || !isRecord(value.dependencies)) return "unknown";
  const { status, dependencies } = value;
  if (httpStatus === 200 && status === "ready" && dependencies.qdrant === "up") return "ready";
  if (httpStatus === 503 && status === "not_ready" && dependencies.qdrant === "down") {
    return "not_ready";
  }
  return "unknown";
}

function isConsistentOnline(d: UnknownRecord): boolean {
  return (
    d.backend === "online" &&
    typeof d.readiness === "string" &&
    d.readiness in QDRANT_BY_READINESS &&
    d.qdrant === QDRANT_BY_READINESS[d.readiness as Readiness]
  );
}

function isConsistentOffline(d: UnknownRecord): boolean {
  return (
    d.backend === "offline" &&
    d.readiness === "unknown" &&
    d.qdrant === "unknown" &&
    isRecord(d.error) &&
    typeof d.error.code === "string"
  );
}

/** Validates the BFF diagnostics payload received by the browser. */
export function isDiagnostics(value: unknown): value is Diagnostics {
  return (
    isRecord(value) &&
    typeof value.request_id === "string" &&
    (isConsistentOnline(value) || isConsistentOffline(value))
  );
}
