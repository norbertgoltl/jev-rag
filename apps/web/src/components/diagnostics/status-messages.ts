import type { Diagnostics } from "@/lib/api/contracts";
import type { StatusProblem } from "./use-backend-status";

export const LOADING_MESSAGE = "Állapot ellenőrzése…";

export function backendLabel(data: Diagnostics | null): string {
  return data?.backend === "online" ? "Elérhető" : "Nem érhető el";
}

export function qdrantLabel(data: Diagnostics | null): string {
  switch (data?.qdrant) {
    case "up":
      return "Elérhető";
    case "down":
      return "Nem áll készen";
    default:
      return "Ismeretlen";
  }
}

function onlineSummary(readiness: Diagnostics["readiness"]): string {
  switch (readiness) {
    case "ready":
      return "A rendszer készen áll.";
    case "not_ready":
      return "A backend elérhető. A Qdrant-kapcsolat még nem áll készen.";
    default:
      return "A backend elérhető. A Qdrant állapota ismeretlen.";
  }
}

export function summaryMessage(data: Diagnostics | null, problem: StatusProblem): string {
  if (data?.backend === "online") return onlineSummary(data.readiness);
  switch (problem) {
    case "timeout":
      return "A backend válaszára várakozás lejárt.";
    case "invalid_response":
      return "A backend válasza nem értelmezhető. Próbáld újra.";
    default:
      return "A backend nem érhető el. Próbáld újra.";
  }
}
