import { useEffect, useRef } from "react";

import { syncBatchFromServer } from "../services/batches";
import { useBatchesStore } from "../state/useBatchesStore";

const HYDRATION_INTERVAL_MS = 60_000;

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

    hydrate();
    const interval = window.setInterval(hydrate, HYDRATION_INTERVAL_MS);

    return () => {
      controller.abort();
      window.clearInterval(interval);
      inflight.current.clear();
    };
  }, [online, batches]);
}
