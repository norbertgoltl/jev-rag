"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { isDiagnostics, type Diagnostics } from "@/lib/api/contracts";
import { StatusIndicator } from "./status-indicator";
import styles from "./backend-status.module.css";
export function BackendStatus() {
 const [data,setData] = useState<Diagnostics | null>(null);
 const [loading,setLoading] = useState(true);
 const [timeout,setTimeoutError] = useState(false);
 const pending = useRef<AbortController | null>(null);
 const check = useCallback(async () => {
  if (pending.current) return;
  const controller = new AbortController(); pending.current = controller;
  try {
   const response = await fetch("/api/backend/status",{cache:"no-store",signal:controller.signal});
   const value: unknown = await response.json();
   if (!isDiagnostics(value) || (response.ok ? value.backend !== "online" : value.backend !== "offline")) throw new Error("Invalid diagnostics");
   if (!controller.signal.aborted) {setData(value);setTimeoutError(response.status === 504);}
  } catch {if (!controller.signal.aborted) setData(null);}
  finally {if (pending.current === controller) {pending.current = null;if (!controller.signal.aborted) setLoading(false);}}
 },[]);
 // State updates in check occur only after the asynchronous fetch completes.
 // eslint-disable-next-line react-hooks/set-state-in-effect
 useEffect(() => {void check(); return () => {pending.current?.abort();pending.current=null;};},[check]);
 return <section className={styles.panel} aria-label="Rendszerállapot"><div aria-live="polite" aria-busy={loading}>
 {loading ? <p>Állapot ellenőrzése…</p> : <><StatusIndicator label="FastAPI" value={data?.backend === "online" ? "Elérhető" : "Nem érhető el"}/><StatusIndicator label="Qdrant" value={data?.qdrant === "up" ? "Elérhető" : data?.qdrant === "down" ? "Nem áll készen" : "Ismeretlen"}/><p>{data?.backend === "online" ? data.readiness === "ready" ? "A rendszer készen áll." : data.readiness === "not_ready" ? "A backend elérhető. A Qdrant-kapcsolat még nem áll készen." : "A backend elérhető. A Qdrant állapota ismeretlen." : timeout ? "A backend válaszára várakozás lejárt." : "A backend nem érhető el. Próbáld újra."}</p></>}
 </div><button disabled={loading} onClick={() => {if (!pending.current) {setLoading(true);setTimeoutError(false);void check();}}}>Újraellenőrzés</button></section>;
}
