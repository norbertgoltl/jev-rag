"use client";
import styles from "./backend-status.module.css";
import { StatusIndicator } from "./status-indicator";
import { LOADING_MESSAGE, backendLabel, qdrantLabel, summaryMessage } from "./status-messages";
import { useBackendStatus } from "./use-backend-status";

export function BackendStatus() {
  const { data, loading, problem, recheck } = useBackendStatus();

  return (
    <section className={styles.panel} aria-label="Rendszerállapot">
      <div aria-live="polite" aria-busy={loading}>
        {loading ? (
          <p>{LOADING_MESSAGE}</p>
        ) : (
          <>
            <StatusIndicator label="FastAPI" value={backendLabel(data)} />
            <StatusIndicator label="Qdrant" value={qdrantLabel(data)} />
            <p>{summaryMessage(data, problem)}</p>
          </>
        )}
      </div>
      <button disabled={loading} onClick={recheck}>
        Újraellenőrzés
      </button>
    </section>
  );
}
