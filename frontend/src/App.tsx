import { useCallback, useEffect, useMemo, useState } from "react";

import { ConnectionBanner } from "./components/ConnectionBanner";
import { BatchSection } from "./components/BatchSection";
import { SyncControls } from "./components/SyncControls";
import { UploadPanel } from "./components/UploadPanel";
import { useOnlineStatus } from "./hooks/useOnlineStatus";
import { useBatchUploader, synchronizePendingBatches } from "./hooks/useBatchUploader";
import { useBatchEvents } from "./hooks/useBatchEvents";
import { loadBatches } from "./services/db";
import { useBatchesStore } from "./state/useBatchesStore";

function App() {
  const online = useOnlineStatus();
  const { setBatches } = useBatchesStore();
  const { submitFiles, retryBatch, uploading } = useBatchUploader({ online });
  const batches = useBatchesStore((state) => state.batches);
  const [syncing, setSyncing] = useState(false);
  const { connected: eventsConnected, available: eventsAvailable } = useBatchEvents(online);

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

  const pendingCount = pendingBatches.length;

  const triggerSync = useCallback(async () => {
    try {
      setSyncing(true);
      const items = await synchronizePendingBatches();
      setBatches(items);
    } finally {
      setSyncing(false);
    }
  }, [setBatches]);

  return (
    <div className="app-shell">
      <header>
        <h1>AUDEX MVP Console</h1>
        <p>Déposez vos fichiers, suivez la synchronisation et consolidez vos audits en mode résilient.</p>
      </header>

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

      <SyncControls
        online={online}
        pendingCount={pendingCount}
        syncing={syncing}
        eventsConnected={eventsConnected}
        eventsAvailable={eventsAvailable}
        onSync={triggerSync}
      />

      <UploadPanel onUpload={handleUpload} isUploading={uploading} online={online} />

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
      />

      {syncedBatches.length === 0 && pendingBatches.length === 0 && (
        <section className="card muted next-steps">
          <h2>Prochaines étapes</h2>
          <ol>
            <li>Brancher le suivi d’analyse en temps réel (SSE/WebSocket).</li>
            <li>Afficher les rapports PDF générés et leur statut de hachage.</li>
            <li>Ajouter l’authentification et la gestion des rôles sur l’interface.</li>
          </ol>
        </section>
      )}
    </div>
  );
}

export default App;
