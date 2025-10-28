import { create } from "zustand";

import type { BatchStatus, BatchSummary } from "../types/batch";

type BatchesState = {
  batches: BatchSummary[];
  initialized: boolean;
  setBatches: (items: BatchSummary[]) => void;
  upsertBatch: (item: BatchSummary) => void;
  updateStatus: (batchId: string, status: BatchStatus, lastError?: string) => void;
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
  updateStatus: (batchId, status, lastError) =>
    set((state) => ({
      batches: state.batches.map((batch) =>
        batch.id === batchId
          ? {
              ...batch,
              status,
              lastError
            }
          : batch
      )
    }))
}));
