import { useCallback, useState } from "react";

import { mapFilesMetadata, persistBatch, updateBatch, loadFiles, loadBatches, getBatch, deleteBatch } from "../services/db";
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

async function uploadToServer(batch: BatchSummary): Promise<void> {
  const files = await loadFiles(batch.id);
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("files", file, file.name);
  });
  await api.post("/ingestion/batches", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
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
        await uploadToServer(batch);
        const updated: BatchSummary = { ...batch, status: "completed" };
        updateStatus(batch.id, "completed");
        await updateBatch(updated);
      } catch (error) {
        const apiError = parseApiError(error);
        const friendly = toFriendlyError(apiError.message, apiError.status);
        console.error("Upload error", apiError);
        updateStatus(batch.id, "failed", { lastError: friendly });
        await updateBatch({ ...batch, status: "failed", lastError: friendly });
      } finally {
        setUploading(false);
      }
    },
    [online, upsertBatch, updateStatus]
  );

  const retryBatch = useCallback(
    async (batchId: string) => {
      const batch = await getBatch(batchId);
      if (!batch) {
        return;
      }
      try {
        await uploadToServer(batch);
        const updated: BatchSummary = { ...batch, status: "completed", lastError: undefined };
        updateStatus(batch.id, "completed", { lastError: undefined });
        await updateBatch(updated);
      } catch (error) {
        const apiError = parseApiError(error);
        const friendly = toFriendlyError(apiError.message, apiError.status);
        updateStatus(batch.id, "failed", { lastError: friendly });
        await updateBatch({ ...batch, status: "failed", lastError: friendly });
      }
    },
    [updateStatus]
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
      await uploadToServer(batch);
      const updated: BatchSummary = { ...batch, status: "completed", lastError: undefined };
      useBatchesStore.getState().updateStatus(batch.id, "completed", { lastError: undefined });
      await updateBatch(updated);
    } catch (error) {
      const apiError = parseApiError(error);
      console.error("Failed to synchronize batch", batch.id, apiError);
      const friendly = toFriendlyError(apiError.message, apiError.status);
      useBatchesStore.getState().updateStatus(batch.id, "failed", { lastError: friendly });
      await updateBatch({ ...batch, status: "failed", lastError: friendly });
    }
  }

  return loadBatches();
}
