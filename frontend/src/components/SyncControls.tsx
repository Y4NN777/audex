type Props = {
  online: boolean;
  pendingCount: number;
  syncing: boolean;
  onSync: () => Promise<void> | void;
  eventsConnected: boolean;
  eventsAvailable: boolean;
  onBulkRetry: () => Promise<void> | void;
  onClearPending: () => Promise<void> | void;
};

export function SyncControls({
  online,
  pendingCount,
  syncing,
  onSync,
  eventsConnected,
  eventsAvailable,
  onBulkRetry,
  onClearPending
}: Props) {
  const hasPending = pendingCount > 0;

  return (
    <section className="card sync-toolbar">
      <div className="status-block">
        <span className={`dot ${online ? "dot-online" : "dot-offline"}`} />
        <div>
          <p className="status-title">{online ? "Connexion active" : "Mode hors-ligne"}</p>
          <p className="muted-text">
            {hasPending
              ? `${pendingCount} lot(s) en attente de synchronisation`
              : "Toutes les données sont à jour"}
          </p>
          <p className="muted-text subtle">
            Flux d'événements : {eventsAvailable ? (eventsConnected ? "connecté" : "déconnecté") : "indisponible"}
          </p>
        </div>
      </div>
      <div className="sync-actions">
        <button type="button" className="sync-button" onClick={() => void onSync()} disabled={!online || !hasPending || syncing}>
          {syncing ? "Synchronisation…" : "Synchroniser"}
        </button>
        <button type="button" className="outline-button" onClick={() => void onBulkRetry()} disabled={!hasPending || syncing}>
          Réessayer tout
        </button>
        <button type="button" className="ghost-button" onClick={() => void onClearPending()} disabled={!hasPending || syncing}>
          Vider la liste
        </button>
      </div>
    </section>
  );
}
