import { useCallback, useState } from "react";

import { mapFilesMetadata, persistBatch, updateBatch, loadFiles, loadBatches } from "../services/db";
import { api, parseApiError } from "../services/api";
import { useBatchesStore } from "../state/useBatchesStore";
import type { BatchStatus, BatchSummary } from "../types/batch";

type UploadResult = {
  submitFiles: (files: File[]) => Promise<void>;
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
  const { upsertBatch, updateStatus } = useBatchesStore();
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
        console.error("Upload error", apiError);
        updateStatus(batch.id, "failed", { lastError: apiError.message });
        await updateBatch({ ...batch, status: "failed", lastError: apiError.message });
      } finally {
        setUploading(false);
      }
    },
    [online, upsertBatch, updateStatus]
  );

  return { submitFiles, uploading };
}

export async function synchronizePendingBatches(): Promise<BatchSummary[]> {
  const batches = await loadBatches();
  const pending = batches.filter((batch) => batch.status === "pending" || batch.status === "failed");

  for (const batch of pending) {
    try {
      await uploadToServer(batch);
      const updated: BatchSummary = { ...batch, status: "completed", lastError: undefined };
      await updateBatch(updated);
    } catch (error) {
      console.error("Failed to synchronize batch", batch.id, parseApiError(error));
    }
  }

  return loadBatches();
}
