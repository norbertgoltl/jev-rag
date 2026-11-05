"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { type Diagnostics, isDiagnostics } from "@/lib/api/contracts";

const STATUS_URL = "/api/backend/status";
const GATEWAY_TIMEOUT = 504;

async function fetchDiagnostics(
  signal: AbortSignal,
): Promise<{ data: Diagnostics; timedOut: boolean }> {
  const response = await fetch(STATUS_URL, { cache: "no-store", signal });
  const value: unknown = await response.json();
  const expectedBackend = response.ok ? "online" : "offline";
  if (!isDiagnostics(value) || value.backend !== expectedBackend) {
    throw new Error("Invalid diagnostics");
  }
  return { data: value, timedOut: response.status === GATEWAY_TIMEOUT };
}

/** Loads backend diagnostics from the BFF, allows a single in-flight request, and exposes a recheck. */
export function useBackendStatus() {
  const [data, setData] = useState<Diagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [timedOut, setTimedOut] = useState(false);
  const pending = useRef<AbortController | null>(null);

  const check = useCallback(async () => {
    if (pending.current) return;
    const controller = new AbortController();
    pending.current = controller;
    try {
      const result = await fetchDiagnostics(controller.signal);
      if (!controller.signal.aborted) {
        setData(result.data);
        setTimedOut(result.timedOut);
      }
    } catch {
      if (!controller.signal.aborted) setData(null);
    } finally {
      if (pending.current === controller) {
        pending.current = null;
        if (!controller.signal.aborted) setLoading(false);
      }
    }
  }, []);

  const recheck = useCallback(() => {
    if (pending.current) return;
    setLoading(true);
    setTimedOut(false);
    void check();
  }, [check]);

  useEffect(() => {
    // State updates in check occur only after the asynchronous fetch completes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void check();
    return () => {
      pending.current?.abort();
      pending.current = null;
    };
  }, [check]);

  return { data, loading, timedOut, recheck };
}
