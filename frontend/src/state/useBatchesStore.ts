import { create } from "zustand";

import type { BatchStatus, BatchSummary } from "../types/batch";

type BatchesState = {
  batches: BatchSummary[];
  initialized: boolean;
  setBatches: (items: BatchSummary[]) => void;
  upsertBatch: (item: BatchSummary) => void;
  mergeBatch: (batchId: string, partial: Partial<BatchSummary>) => void;
  updateStatus: (batchId: string, status: BatchStatus, options?: { lastError?: string; report?: BatchSummary["report"] }) => void;
  removeBatch: (batchId: string) => void;
};

export const useBatchesStore = create<BatchesState>((set) => ({
  batches: [],
  initialized: false,
  setBatches: (items) =>
    set(() => ({
      batches: items,
      initialized: true
    })),
  upsertBatch: (item) =>
    set((state) => {
      const next = state.batches.filter((batch) => batch.id !== item.id);
      next.unshift(item);
      return { batches: next };
    }),
  mergeBatch: (batchId, partial) =>
    set((state) => ({
      batches: state.batches.map((batch) => (batch.id === batchId ? { ...batch, ...partial } : batch))
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
  removeBatch: (batchId) =>
    set((state) => ({
      batches: state.batches.filter((batch) => batch.id !== batchId)
    }))
}));
