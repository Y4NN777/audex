import { useEffect, useRef, useState } from "react";

import { API_BASE_URL } from "../services/api";
import { appendTimelineEntry, mergeBatchRecord } from "../services/db";
import { resolveReportUrl } from "../services/reports";
import { useBatchesStore } from "../state/useBatchesStore";
import type { BatchStatus, BatchSummary, BatchTimelineEntry, TimelineEventKind } from "../types/batch";

type BatchEventPayload = {
  batchId: string;
  status?: BatchStatus;
  error?: string;
  reportHash?: string;
  reportUrl?: string;
  stage?: {
    eventId: string;
    code: string;
    label: string;
    kind: TimelineEventKind;
    timestamp: string;
    details?: Record<string, unknown>;
    progress?: number;
  };
};

const EVENTS_ENDPOINT = `${API_BASE_URL}/api/v1/ingestion/events`;

export function useBatchEvents(enabled: boolean) {
  const mergeBatch = useBatchesStore((state) => state.mergeBatch);
  const addTimelineEntry = useBatchesStore((state) => state.addTimelineEntry);
  const setProgress = useBatchesStore((state) => state.setProgress);
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

    eventSource.onmessage = async (event) => {
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
            downloadUrl: resolveReportUrl(payload.batchId)
          };
        }

        if (Object.keys(updates).length > 0) {
          mergeBatch(payload.batchId, updates);
          await mergeBatchRecord(payload.batchId, updates);
        }

        if (payload.stage) {
          const entry: BatchTimelineEntry = {
            id: payload.stage.eventId,
            stage: payload.stage.code,
            label: payload.stage.label,
            timestamp: payload.stage.timestamp,
            kind: payload.stage.kind,
            details: payload.stage.details ?? {},
            progress: payload.stage.progress
          };
          addTimelineEntry(payload.batchId, entry);
          await appendTimelineEntry(payload.batchId, entry);
          if (typeof entry.progress === "number") {
            setProgress(payload.batchId, entry.progress);
          }
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
  }, [enabled, mergeBatch, addTimelineEntry, setProgress]);

  return { connected, available };
}
