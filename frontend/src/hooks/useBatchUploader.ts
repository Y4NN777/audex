import { useCallback, useState } from "react";

import { mapFilesMetadata, persistBatch, updateBatch, loadFiles, loadBatches } from "../services/db";
import { useBatchesStore } from "../state/useBatchesStore";
import type { BatchStatus, BatchSummary } from "../types/batch";

type UploadResult = {
  submitFiles: (files: File[]) => Promise<void>;
  uploading: boolean;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function uploadToServer(batch: BatchSummary): Promise<Response> {
  const files = await loadFiles(batch.id);
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("files", file, file.name);
  });
  const response = await fetch(`${API_URL}/api/v1/ingestion/batches`, {
    method: "POST",
    body: formData
  });
  return response;
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
        const response = await uploadToServer(batch);
        if (!response.ok) {
          const detail = await response.text();
          updateStatus(batch.id, "failed", detail);
          await updateBatch({ ...batch, status: "failed", lastError: detail });
          return;
        }
        const updated: BatchSummary = { ...batch, status: "completed" };
        updateStatus(batch.id, "completed");
        await updateBatch(updated);
      } catch (error) {
        console.error("Upload error", error);
        updateStatus(batch.id, "failed", (error as Error).message);
        await updateBatch({ ...batch, status: "failed", lastError: (error as Error).message });
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
      const response = await uploadToServer(batch);
      if (!response.ok) {
        continue;
      }
      const updated: BatchSummary = { ...batch, status: "completed", lastError: undefined };
      await updateBatch(updated);
    } catch (error) {
      console.error("Failed to synchronize batch", batch.id, error);
    }
  }

  return loadBatches();
}
