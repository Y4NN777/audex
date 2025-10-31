import { useCallback, useEffect, useMemo, useState } from "react";

import { ConnectionBanner } from "./components/ConnectionBanner";
import { BatchSection } from "./components/BatchSection";
import { StatsStrip, buildStats } from "./components/StatsStrip";
import { SyncControls } from "./components/SyncControls";
import { UploadPanel } from "./components/UploadPanel";
import { ReportHero } from "./components/ReportHero";
import { ObservationsPanel } from "./components/ObservationsPanel";
import { AnnexesPanel } from "./components/AnnexesPanel";
import { TimelinePanel } from "./components/TimelinePanel";
import { SummaryPanel } from "./components/SummaryPanel";
import { useOnlineStatus } from "./hooks/useOnlineStatus";
import { useBatchUploader, synchronizePendingBatches } from "./hooks/useBatchUploader";
import { useBatchEvents } from "./hooks/useBatchEvents";
import { loadBatches } from "./services/db";
import { useBatchesStore } from "./state/useBatchesStore";
import { useBatchHydrator } from "./hooks/useBatchHydrator";
import { syncBatchFromServer } from "./services/batches";
import { formatBytes } from "./utils/format";

function App() {
  const online = useOnlineStatus();
  const { setBatches } = useBatchesStore();
  const { submitFiles, retryBatch, removeBatch, uploading } = useBatchUploader({ online });
  const batches = useBatchesStore((state) => state.batches);
  const [syncing, setSyncing] = useState(false);
  const { connected: eventsConnected, available: eventsAvailable } = useBatchEvents(online);
  useBatchHydrator(online);

  useEffect(() => {
    let cancelled = false;
    void loadBatches().then((items) => {
      if (!cancelled) {
        setBatches(items);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [setBatches]);

  useEffect(() => {
    if (!online) {
      return;
    }
    let cancelled = false;
    setSyncing(true);
    void synchronizePendingBatches()
      .then((items) => {
        if (!cancelled) {
          setBatches(items);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSyncing(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [online, setBatches]);

  const handleUpload = useCallback(async (files: File[]) => {
    await submitFiles(files);
    const items = online ? await synchronizePendingBatches() : await loadBatches();
    setBatches(items);
  }, [online, setBatches, submitFiles]);

  const pendingBatches = useMemo(
    () => batches.filter((batch) => batch.status === "pending" || batch.status === "failed" || batch.status === "uploading"),
    [batches]
  );
  const syncedBatches = useMemo(
    () => batches.filter((batch) => batch.status === "completed" || batch.status === "processing"),
    [batches]
  );
  const completedBatches = useMemo(() => batches.filter((batch) => batch.status === "completed"), [batches]);

  const pendingCount = pendingBatches.length;

  const { averageRisk, criticalObservations } = useMemo(() => {
    if (completedBatches.length === 0) {
      return { averageRisk: null, criticalObservations: 0 };
    }
    const riskValues = completedBatches
      .map((batch) => batch.insights?.risk?.normalizedScore)
      .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
    const avg = riskValues.length
      ? riskValues.reduce((total, value) => total + value, 0) / riskValues.length
      : null;
    const critical = completedBatches.reduce((acc, batch) => {
      const observations = batch.observations ?? [];
      return acc + observations.filter((obs) => (obs.severity ?? "").toLowerCase() === "high").length;
    }, 0);
    return { averageRisk: avg, criticalObservations: critical };
  }, [completedBatches]);

  const stats = useMemo(() => {
    const totalFiles = batches.reduce((total, batch) => total + batch.files.length, 0);
    const totalSizeBytes = batches.reduce(
      (total, batch) => total + batch.files.reduce((sum, file) => sum + file.size, 0),
      0
    );

    return buildStats({
      totalBatches: batches.length,
      pending: pendingCount,
      totalFiles,
      totalSize: formatBytes(totalSizeBytes),
      completed: completedBatches.length,
      averageRisk,
      criticalObservations
    });
  }, [batches, pendingCount, completedBatches.length, averageRisk, criticalObservations]);

  const triggerSync = useCallback(async () => {
    try {
      setSyncing(true);
      const items = await synchronizePendingBatches();
      setBatches(items);
    } finally {
      setSyncing(false);
    }
  }, [setBatches]);

  const handleBulkRetry = useCallback(async () => {
    for (const batch of pendingBatches) {
      await retryBatch(batch.id);
    }
    const items = await loadBatches();
    setBatches(items);
  }, [pendingBatches, retryBatch, setBatches]);

  const handleClearPending = useCallback(async () => {
    for (const batch of pendingBatches) {
      await removeBatch(batch.id);
    }
    const items = await loadBatches();
    setBatches(items);
  }, [pendingBatches, removeBatch, setBatches]);

  const highlightedBatch = useMemo(() => {
    if (completedBatches.length > 0) {
      return completedBatches[0];
    }
    if (syncedBatches.length > 0) {
      return syncedBatches[0];
    }
    return null;
  }, [completedBatches, syncedBatches]);

  const handleRefreshHighlight = useCallback(() => {
    if (!highlightedBatch || !online) {
      return;
    }
    void syncBatchFromServer(highlightedBatch.id);
  }, [highlightedBatch, online]);

  useEffect(() => {
    if (!online || !highlightedBatch) {
      return;
    }
    const requiresHydration =
      !highlightedBatch.insights ||
      !highlightedBatch.insights.syncedAt ||
      (highlightedBatch.observations?.length ?? 0) === 0 ||
      (highlightedBatch.ocrTexts?.length ?? 0) === 0;
    if (requiresHydration) {
      void syncBatchFromServer(highlightedBatch.id);
    }
  }, [online, highlightedBatch]);

  return (
    <div className="app-shell">
      <ReportHero batch={highlightedBatch} onRefresh={handleRefreshHighlight} />
      <ConnectionBanner
        syncing={syncing}
        onBackOnline={async () => {
          setSyncing(true);
          try {
            const items = await synchronizePendingBatches();
            setBatches(items);
          } finally {
            setSyncing(false);
          }
        }}
      />

      <StatsStrip stats={stats} />

      <div className="workspace-grid">
        <div className="workspace-main">
          <SyncControls
            online={online}
            pendingCount={pendingCount}
            syncing={syncing}
            eventsConnected={eventsConnected}
            eventsAvailable={eventsAvailable}
            onSync={triggerSync}
            onBulkRetry={handleBulkRetry}
            onClearPending={handleClearPending}
          />

          <UploadPanel onUpload={handleUpload} isUploading={uploading} online={online} />

          <SummaryPanel batch={highlightedBatch} />

          <div className="insights-grid">
            <ObservationsPanel batch={highlightedBatch} />
            <AnnexesPanel batch={highlightedBatch} />
          </div>
        </div>

        <aside className="workspace-side">
          <TimelinePanel batch={highlightedBatch} />
        </aside>
      </div>

      <div className="batches-grid">
        <BatchSection
          title="Lots synchronisés"
          batches={syncedBatches}
          emptyMessage="Aucun lot n'a encore été envoyé."
          onRetry={retryBatch}
        />

        <BatchSection
          title="Lots en attente"
          batches={pendingBatches}
          emptyMessage="Pas de lot en attente de synchronisation."
          onRetry={retryBatch}
          onRemove={removeBatch}
        />
      </div>

      {syncedBatches.length === 0 && pendingBatches.length === 0 && (
        <section className="card muted next-steps">
          <h2>Comment tester le flux d’analyse</h2>
          <ol>
            <li>Déposez un lot de fichiers pour lancer automatiquement l’analyse.</li>
            <li>Regardez la chronologie : chaque étape s’affiche en direct pendant le traitement.</li>
            <li>Téléchargez le PDF généré et notez le code d’intégrité (hash) pour vérification ultérieure.</li>
          </ol>
        </section>
      )}
    </div>
  );
}

export default App;
