import "server-only";
import { backendGet } from "./backend-client";
import { type Diagnostics, isStatus, readiness } from "./contracts";
import { BackendError } from "./errors";
export async function diagnose(requestId: string): Promise<{status: number; body: Diagnostics}> {
 const [system, ready] = await Promise.allSettled([backendGet("/api/v1/system/status", requestId), backendGet("/health/ready", requestId)]);
 if (system.status === "rejected" || system.value.status !== 200 || !isStatus(system.value.body)) {
  const code = system.status === "rejected" && system.reason instanceof BackendError ? system.reason.code : "BACKEND_INVALID_RESPONSE";
  return {status: code === "BACKEND_TIMEOUT" ? 504 : code === "BACKEND_UNREACHABLE" ? 503 : 502, body: {backend:"offline",readiness:"unknown",qdrant:"unknown",request_id:requestId,error:{code,message:"Backend service unavailable"}}};
 }
 const state = ready.status === "fulfilled" ? readiness(ready.value.body, ready.value.status) : "unknown";
 return {status:200,body:{backend:"online",readiness:state,qdrant:state === "ready" ? "up" : state === "not_ready" ? "down" : "unknown",request_id:requestId}};
}
