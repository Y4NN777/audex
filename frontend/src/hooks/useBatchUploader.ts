import { useCallback, useState } from "react";

import {
  mapFilesMetadata,
  persistBatch,
  updateBatch,
  loadFiles,
  loadBatches,
  getBatch,
  deleteBatch,
  mergeBatchRecord
} from "../services/db";
import { api, parseApiError } from "../services/api";
import { useBatchesStore } from "../state/useBatchesStore";
import type { BatchStatus, BatchSummary } from "../types/batch";
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
};

async function uploadToServer(batch: BatchSummary): Promise<UploadResponse> {
  const files = await loadFiles(batch.id);
  const formData = new FormData();
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
    files: mapFilesMetadata(files)
  };
}

export function useBatchUploader({ online }: { online: boolean }): UploadResult {
  const { upsertBatch, updateStatus, mergeBatch, removeBatch: removeFromStore } = useBatchesStore();
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
        upsertBatch(batch);
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
        await mergePersisted(batch.id, { status: "processing" });

        const response = await uploadToServer(batch);
        const normalizedStatus = response.status as BatchStatus;
        const report = response.report_hash
          ? {
              hash: response.report_hash,
              downloadUrl: `/api/v1/ingestion/reports/${batch.id}`
            }
          : undefined;
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
    [online, upsertBatch, updateStatus, mergePersisted]
  );

  const retryBatch = useCallback(
    async (batchId: string) => {
      const batch = await getBatch(batchId);
      if (!batch) {
        return;
      }
      try {
        updateStatus(batch.id, "processing");
        await mergePersisted(batch.id, { status: "processing" });

        const response = await uploadToServer(batch);
        const normalizedStatus = response.status as BatchStatus;
        const report = response.report_hash
          ? {
              hash: response.report_hash,
              downloadUrl: `/api/v1/ingestion/reports/${batch.id}`
            }
          : undefined;
        updateStatus(batch.id, normalizedStatus, { lastError: undefined, report });
        await mergePersisted(batch.id, { status: normalizedStatus, lastError: undefined, report });
      } catch (error) {
        const apiError = parseApiError(error);
        const friendly = toFriendlyError(apiError.message, apiError.status);
        updateStatus(batch.id, "failed", { lastError: friendly });
        await mergePersisted(batch.id, { status: "failed", lastError: friendly });
      }
    },
    [updateStatus, mergePersisted]
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
            downloadUrl: `/api/v1/ingestion/reports/${batch.id}`
          }
        : undefined;
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
