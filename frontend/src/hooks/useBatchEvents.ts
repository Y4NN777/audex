import { useEffect, useRef, useState } from "react";

import { API_BASE_URL } from "../services/api";
import { useBatchesStore } from "../state/useBatchesStore";
import type { BatchStatus, BatchSummary } from "../types/batch";

type BatchEventPayload = {
  batchId: string;
  status?: BatchStatus;
  error?: string;
  reportHash?: string;
  reportUrl?: string;
};

const EVENTS_ENDPOINT = `${API_BASE_URL}/ingestion/events`;

export function useBatchEvents(enabled: boolean) {
  const mergeBatch = useBatchesStore((state) => state.mergeBatch);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled) {
      if (sourceRef.current) {
        sourceRef.current.close();
        sourceRef.current = null;
      }
      setConnected(false);
      return;
    }

    const eventSource = new EventSource(EVENTS_ENDPOINT, { withCredentials: false });
    sourceRef.current = eventSource;

    eventSource.onopen = () => setConnected(true);
    eventSource.onerror = () => {
      setConnected(false);
    };

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as BatchEventPayload;
        if (!payload.batchId) return;

        mergeBatch(payload.batchId, {
          status: payload.status,
          lastError: payload.error,
          report: payload.reportHash || payload.reportUrl
            ? {
                hash: payload.reportHash,
                downloadUrl: payload.reportUrl ?? `${API_BASE_URL}/reports/${payload.batchId}`
              }
            : undefined
        } as Partial<BatchSummary>);
      } catch (error) {
        console.error("Failed to parse batch event", error);
      }
    };

    return () => {
      eventSource.close();
      sourceRef.current = null;
      setConnected(false);
    };
  }, [enabled, mergeBatch]);

  return { connected };
}
