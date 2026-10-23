import "server-only";
export function getConfig() {
 const raw = process.env.BACKEND_API_URL ?? (process.env.NODE_ENV === "production" ? undefined : "http://127.0.0.1:8000");
 if (!raw) throw new Error("BACKEND_API_URL is required");
 const url = new URL(raw);
 if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== "/") throw new Error("Invalid BACKEND_API_URL");
 const timeout = Number(process.env.BACKEND_TIMEOUT_MS ?? 2000);
 if (!Number.isSafeInteger(timeout) || timeout <= 0) throw new Error("Invalid BACKEND_TIMEOUT_MS");
 return { url: url.origin, timeout };
}
