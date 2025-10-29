import { useCallback, useState } from "react";

import {
  mapFilesMetadata,
  persistBatch,
  loadFiles,
  loadBatches,
  getBatch,
  deleteBatch,
  mergeBatchRecord,
  appendTimelineEntry
} from "../services/db";
import { API_BASE_URL, api, parseApiError } from "../services/api";
import { useBatchesStore } from "../state/useBatchesStore";
import type { BatchStatus, BatchSummary, BatchTimelineEntry, ServerTimelineEvent } from "../types/batch";
import { resolveReportUrl } from "../services/reports";
import { toFriendlyError } from "../utils/errors";

type UploadResult = {
  submitFiles: (files: File[]) => Promise<void>;
  retryBatch: (batchId: string) => Promise<void>;
  removeBatch: (batchId: string) => Promise<void>;
  uploading: boolean;
};

type UploadResponse = {
  batch_id: string;
  status: BatchStatus;
  report_hash?: string | null;
  stored_at: string;
  timeline?: ServerTimelineEvent[];
  report_url?: string | null;
};

async function uploadToServer(batch: BatchSummary): Promise<UploadResponse> {
  const files = await loadFiles(batch.id);
  const formData = new FormData();
  formData.append("client_batch_id", batch.id);
  files.forEach((file) => {
    formData.append("files", file, file.name);
  });
  const response = await api.post("/ingestion/batches", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return response.data as UploadResponse;
}

function createBatch(files: File[], status: BatchStatus): BatchSummary {
  const batchId = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `batch-${Date.now()}`;
  return {
    id: batchId,
    createdAt: new Date().toISOString(),
    status,
    files: mapFilesMetadata(files),
     progress: status === "completed" ? 100 : 0,
    timeline: [
      {
        id: `${batchId}-created`,
        stage: "client:queued",
        label: "Fichiers ajoutés depuis le poste client",
        timestamp: new Date().toISOString(),
        kind: "info",
        details: { fileCount: files.length },
        progress: 0
      }
    ]
  };
}

export function useBatchUploader({ online }: { online: boolean }): UploadResult {
  const { upsertBatch, updateStatus, mergeBatch, removeBatch: removeFromStore, setProgress } = useBatchesStore();
  const [uploading, setUploading] = useState(false);

  const mergePersisted = useCallback(
    async (batchId: string, partial: Partial<BatchSummary>) => {
      mergeBatch(batchId, partial);
      await mergeBatchRecord(batchId, partial);
    },
    [mergeBatch]
  );

  const submitFiles = useCallback(
    async (files: File[]) => {
      if (!files.length) {
        return;
      }

      const initialStatus: BatchStatus = online ? "uploading" : "pending";
      const batch = createBatch(files, initialStatus);

      try {
        await persistBatch(batch, files);
        upsertBatch({ ...batch, progress: 0 });
      } catch (error) {
        console.error("Failed to persist batch locally", error);
        throw error;
      }

      if (!online) {
        return;
      }

      setUploading(true);
      try {
        updateStatus(batch.id, "processing");
        setProgress(batch.id, 10);
        await mergePersisted(batch.id, { status: "processing", progress: 10 });

        const response = await uploadToServer(batch);
        const normalizedStatus = response.status as BatchStatus;
        const report = response.report_hash
          ? {
              hash: response.report_hash,
              downloadUrl: response.report_url
                ? absolutizeReportUrl(response.report_url)
                : resolveReportUrl(batch.id)
            }
          : undefined;
        const latestProgress = await persistTimelineEvents(batch.id, response.timeline);
        if (typeof latestProgress === "number") {
          setProgress(batch.id, latestProgress);
          await mergePersisted(batch.id, { progress: latestProgress });
        }
        updateStatus(batch.id, normalizedStatus, { lastError: undefined, report });
        await mergePersisted(batch.id, { status: normalizedStatus, lastError: undefined, report });
      } catch (error) {
        const apiError = parseApiError(error);
        const friendly = toFriendlyError(apiError.message, apiError.status);
        console.error("Upload error", apiError);
        updateStatus(batch.id, "failed", { lastError: friendly });
        await mergePersisted(batch.id, { status: "failed", lastError: friendly });
      } finally {
        setUploading(false);
      }
    },
    [online, upsertBatch, updateStatus, mergePersisted, setProgress]
  );

  const retryBatch = useCallback(
    async (batchId: string) => {
      const batch = await getBatch(batchId);
      if (!batch) {
        return;
      }
      try {
        updateStatus(batch.id, "processing");
        setProgress(batch.id, 10);
        await mergePersisted(batch.id, { status: "processing", progress: 10 });

        const response = await uploadToServer(batch);
        const normalizedStatus = response.status as BatchStatus;
        const report = response.report_hash
          ? {
              hash: response.report_hash,
              downloadUrl: response.report_url
                ? absolutizeReportUrl(response.report_url)
                : resolveReportUrl(batch.id)
            }
          : undefined;
        const latestProgress = await persistTimelineEvents(batch.id, response.timeline);
        if (typeof latestProgress === "number") {
          setProgress(batch.id, latestProgress);
          await mergePersisted(batch.id, { progress: latestProgress });
        }
        updateStatus(batch.id, normalizedStatus, { lastError: undefined, report });
        await mergePersisted(batch.id, { status: normalizedStatus, lastError: undefined, report });
      } catch (error) {
        const apiError = parseApiError(error);
        const friendly = toFriendlyError(apiError.message, apiError.status);
        updateStatus(batch.id, "failed", { lastError: friendly });
        await mergePersisted(batch.id, { status: "failed", lastError: friendly });
      }
    },
    [updateStatus, mergePersisted, setProgress]
  );

  const removeBatch = useCallback(
    async (batchId: string) => {
      await deleteBatch(batchId);
      removeFromStore(batchId);
    },
    [removeFromStore]
  );

  return { submitFiles, retryBatch, uploading, removeBatch };
}

export async function synchronizePendingBatches(): Promise<BatchSummary[]> {
  const batches = await loadBatches();
  const pending = batches.filter((batch) => batch.status === "pending" || batch.status === "failed");

  for (const batch of pending) {
    try {
      useBatchesStore.getState().updateStatus(batch.id, "processing");
      await mergeBatchRecord(batch.id, { status: "processing" });

      const response = await uploadToServer(batch);
      const normalizedStatus = response.status as BatchStatus;
      const report = response.report_hash
        ? {
            hash: response.report_hash,
            downloadUrl: response.report_url
              ? absolutizeReportUrl(response.report_url)
              : resolveReportUrl(batch.id)
          }
        : undefined;
      const latestProgress = await persistTimelineEvents(batch.id, response.timeline);
      if (typeof latestProgress === "number") {
        useBatchesStore.getState().setProgress(batch.id, latestProgress);
        await mergeBatchRecord(batch.id, { progress: latestProgress });
      }
      useBatchesStore.getState().updateStatus(batch.id, normalizedStatus, { lastError: undefined, report });
      await mergeBatchRecord(batch.id, { status: normalizedStatus, lastError: undefined, report });
    } catch (error) {
      const apiError = parseApiError(error);
      console.error("Failed to synchronize batch", batch.id, apiError);
      const friendly = toFriendlyError(apiError.message, apiError.status);
      useBatchesStore.getState().updateStatus(batch.id, "failed", { lastError: friendly });
      await mergeBatchRecord(batch.id, { status: "failed", lastError: friendly });
    }
  }

  return loadBatches();
}

function mapServerTimelineEvent(event: ServerTimelineEvent): BatchTimelineEntry {
  return {
    id: event.eventId,
    stage: event.code,
    label: event.label,
    timestamp: event.timestamp,
    kind: event.kind ?? "info",
    details: event.details,
    progress: event.progress
  };
}

async function persistTimelineEvents(batchId: string, events: ServerTimelineEvent[] | undefined): Promise<number | undefined> {
  if (!events || events.length === 0) {
    return undefined;
  }
  const entries = events.map(mapServerTimelineEvent);
  const addTimeline = useBatchesStore.getState().addTimelineEntry;
  let latestProgress = -1;

  for (const entry of entries) {
    addTimeline(batchId, entry);
    await appendTimelineEntry(batchId, entry);
    if (typeof entry.progress === "number") {
      latestProgress = Math.max(latestProgress, entry.progress);
    }
  }

  return latestProgress >= 0 ? latestProgress : undefined;
}

function absolutizeReportUrl(reportUrl: string): string {
  if (reportUrl.startsWith("http://") || reportUrl.startsWith("https://")) {
    return reportUrl;
  }
  const normalized = reportUrl.startsWith("/") ? reportUrl.slice(1) : reportUrl;
  return `${API_BASE_URL.replace(/\/$/, "")}/${normalized}`;
}
