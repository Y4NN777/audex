import { useEffect, useRef } from "react";

import { syncBatchFromServer } from "../services/batches";
import { useBatchesStore } from "../state/useBatchesStore";

const HYDRATION_INTERVAL_MS = 60_000;
const HYDRATION_INTERVAL_FAST_MS = 15_000;
const FRESH_BATCH_WINDOW_MS = 5 * 60_000;

export function useBatchHydrator(online: boolean) {
  const batches = useBatchesStore((state) => state.batches);
  const inflight = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!online) {
      inflight.current.clear();
      return;
    }

    const controller = new AbortController();

    const hydrate = async () => {
      const targets = batches.filter((batch) => {
        if (batch.status === "failed" || batch.status === "pending") {
          return false;
        }
        if (inflight.current.has(batch.id)) {
          return false;
        }
        if (!batch.insights || !batch.insights.syncedAt) {
          return true;
        }
        const lastSynced = Date.parse(batch.insights.syncedAt);
        if (Number.isNaN(lastSynced)) {
          return true;
        }
        return Date.now() - lastSynced > HYDRATION_INTERVAL_MS;
      });

      for (const batch of targets) {
        if (controller.signal.aborted) {
          break;
        }
        inflight.current.add(batch.id);
        try {
          await syncBatchFromServer(batch.id);
        } finally {
          inflight.current.delete(batch.id);
        }
      }
    };

    const pickInterval = () => {
      const now = Date.now();
      const hasRecentProcessing = batches.some((batch) => {
        if (batch.status !== "processing" && batch.status !== "uploading") {
          return false;
        }
        const createdAt = Date.parse(batch.createdAt);
        if (Number.isNaN(createdAt)) {
          return true;
        }
        return now - createdAt < FRESH_BATCH_WINDOW_MS;
      });
      return hasRecentProcessing ? HYDRATION_INTERVAL_FAST_MS : HYDRATION_INTERVAL_MS;
    };

    let timeoutId: number | null = null;

    const loop = async () => {
      await hydrate();
      if (controller.signal.aborted) {
        return;
      }
      const delay = pickInterval();
      timeoutId = window.setTimeout(loop, delay);
    };

    void loop();

    return () => {
      controller.abort();
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
      inflight.current.clear();
    };
  }, [online, batches]);
}
