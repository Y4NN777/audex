import { create } from "zustand";

import type { BatchStatus, BatchSummary, BatchTimelineEntry } from "../types/batch";

const ensureProgress = (batch: BatchSummary): BatchSummary => ({
  ...batch,
  progress: typeof batch.progress === "number" ? batch.progress : 0
});

type BatchesState = {
  batches: BatchSummary[];
  initialized: boolean;
  setBatches: (items: BatchSummary[]) => void;
  upsertBatch: (item: BatchSummary) => void;
  mergeBatch: (batchId: string, partial: Partial<BatchSummary>) => void;
  updateStatus: (batchId: string, status: BatchStatus, options?: { lastError?: string; report?: BatchSummary["report"] }) => void;
  removeBatch: (batchId: string) => void;
  addTimelineEntry: (batchId: string, entry: BatchTimelineEntry) => void;
  setProgress: (batchId: string, progress: number) => void;
};

export const useBatchesStore = create<BatchesState>((set) => ({
  batches: [],
  initialized: false,
  setBatches: (items) =>
    set(() => ({
      batches: items.map(ensureProgress),
      initialized: true
    })),
  upsertBatch: (item) =>
    set((state) => {
      const next = state.batches.filter((batch) => batch.id !== item.id);
      next.unshift(ensureProgress(item));
      return { batches: next };
    }),
  mergeBatch: (batchId, partial) =>
    set((state) => ({
      batches: state.batches.map((batch) =>
        batch.id === batchId ? ensureProgress({ ...batch, ...partial }) : batch
      )
    })),
  updateStatus: (batchId, status, options) =>
    set((state) => ({
      batches: state.batches.map((batch) =>
        batch.id === batchId
          ? {
              ...batch,
              status,
              lastError: options?.lastError ?? batch.lastError,
              report: options?.report ?? batch.report
            }
          : batch
      )
    })),
  addTimelineEntry: (batchId, entry) =>
    set((state) => ({
      batches: state.batches.map((batch) =>
        batch.id === batchId
          ? {
              ...batch,
              timeline: batch.timeline.some((existing) => existing.id === entry.id)
                ? batch.timeline
                : [...batch.timeline, entry].sort((a, b) => a.timestamp.localeCompare(b.timestamp)),
              progress:
                entry.progress !== undefined
                  ? Math.max(batch.progress, entry.progress)
                  : batch.progress
            }
          : batch
      )
    })),
  setProgress: (batchId, progress) =>
    set((state) => ({
      batches: state.batches.map((batch) =>
        batch.id === batchId ? { ...batch, progress: Math.max(progress, batch.progress) } : batch
      )
    })),
  removeBatch: (batchId) =>
    set((state) => ({
      batches: state.batches.filter((batch) => batch.id !== batchId)
    }))
}));
