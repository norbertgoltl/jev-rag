export type Diagnostics = { backend: "online" | "offline"; readiness: "ready" | "not_ready" | "unknown"; qdrant: "up" | "down" | "unknown"; request_id: string; error?: {code: string; message: string} };
export function isStatus(value: unknown): boolean {
 return typeof value === "object" && value !== null && "service" in value && value.service === "api" && "status" in value && value.status === "ok";
}
export function readiness(value: unknown, status: number): "ready" | "not_ready" | "unknown" {
 if (typeof value !== "object" || value === null || !("status" in value) || !("dependencies" in value)) return "unknown";
 const deps = value.dependencies;
 if (typeof deps !== "object" || deps === null || !("qdrant" in deps)) return "unknown";
 if (status === 200 && value.status === "ready" && deps.qdrant === "up") return "ready";
 if (status === 503 && value.status === "not_ready" && deps.qdrant === "down") return "not_ready";
 return "unknown";
}
export function isDiagnostics(value: unknown): value is Diagnostics {
 if (typeof value !== "object" || value === null) return false;
 const d = value as Partial<Diagnostics>;
 return typeof d.request_id === "string" && ((d.backend === "online" && ((d.readiness === "ready" && d.qdrant === "up") || (d.readiness === "not_ready" && d.qdrant === "down") || (d.readiness === "unknown" && d.qdrant === "unknown"))) || (d.backend === "offline" && d.readiness === "unknown" && d.qdrant === "unknown" && typeof d.error?.code === "string"));
}
