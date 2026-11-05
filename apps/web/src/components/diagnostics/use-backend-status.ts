"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { type Diagnostics, isDiagnostics } from "@/lib/api/contracts";

const STATUS_URL = "/api/backend/status";
const GATEWAY_TIMEOUT = 504;

/** Why the latest check produced no usable diagnostics, or null when it did. */
export type StatusProblem = "timeout" | "unreachable" | "invalid_response" | null;

class InvalidDiagnosticsError extends Error {}

async function readDiagnostics(response: Response, signal: AbortSignal): Promise<Diagnostics> {
  let value: unknown;
  try {
    value = await response.json();
  } catch (error) {
    if (signal.aborted) throw error;
    throw new InvalidDiagnosticsError("Diagnostics response is not JSON");
  }
  const expectedBackend = response.ok ? "online" : "offline";
  if (!isDiagnostics(value) || value.backend !== expectedBackend) {
    throw new InvalidDiagnosticsError("Diagnostics response has an unexpected shape");
  }
  return value;
}

async function fetchDiagnostics(
  signal: AbortSignal,
): Promise<{ data: Diagnostics; problem: StatusProblem }> {
  const response = await fetch(STATUS_URL, { cache: "no-store", signal });
  const data = await readDiagnostics(response, signal);
  return { data, problem: response.status === GATEWAY_TIMEOUT ? "timeout" : null };
}

function problemOf(error: unknown): StatusProblem {
  return error instanceof InvalidDiagnosticsError ? "invalid_response" : "unreachable";
}

/** Loads backend diagnostics from the BFF, allows a single in-flight request, and exposes a recheck. */
export function useBackendStatus() {
  const [data, setData] = useState<Diagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<StatusProblem>(null);
  const pending = useRef<AbortController | null>(null);

  const check = useCallback(async () => {
    if (pending.current) return;
    const controller = new AbortController();
    pending.current = controller;
    try {
      const result = await fetchDiagnostics(controller.signal);
      if (!controller.signal.aborted) {
        setData(result.data);
        setProblem(result.problem);
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        setData(null);
        setProblem(problemOf(error));
      }
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
    setProblem(null);
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

  return { data, loading, problem, recheck };
}
