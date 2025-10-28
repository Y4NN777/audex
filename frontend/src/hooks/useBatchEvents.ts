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

const EVENTS_ENDPOINT = `${API_BASE_URL}/api/v1/ingestion/events`;

export function useBatchEvents(enabled: boolean) {
  const mergeBatch = useBatchesStore((state) => state.mergeBatch);
  const [connected, setConnected] = useState(false);
   const [available, setAvailable] = useState(true);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled) {
      if (sourceRef.current) {
        sourceRef.current.close();
        sourceRef.current = null;
      }
      setConnected(false);
      setAvailable(true);
      return;
    }

    const eventSource = new EventSource(EVENTS_ENDPOINT, { withCredentials: false });
    sourceRef.current = eventSource;
    let opened = false;

    eventSource.onopen = () => {
      opened = true;
      setAvailable(true);
      setConnected(true);
    };
    eventSource.onerror = () => {
      setConnected(false);
      if (!opened) {
        setAvailable(false);
        eventSource.close();
        sourceRef.current = null;
      }
    };

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as BatchEventPayload;
        if (!payload.batchId) return;

        const updates: Partial<BatchSummary> = {};
        if (payload.status) {
          updates.status = payload.status;
        }
        if (payload.error !== undefined) {
          updates.lastError = payload.error;
        }
        if (payload.reportHash || payload.reportUrl) {
          updates.report = {
            hash: payload.reportHash,
            downloadUrl: payload.reportUrl ?? `${API_BASE_URL}/api/v1/reports/${payload.batchId}`
          };
        }

        if (Object.keys(updates).length > 0) {
          mergeBatch(payload.batchId, updates);
        }
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

  return { connected, available };
}
