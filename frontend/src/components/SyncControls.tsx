type Props = {
  online: boolean;
  pendingCount: number;
  syncing: boolean;
  onSync: () => Promise<void> | void;
  eventsConnected: boolean;
  eventsAvailable: boolean;
};

export function SyncControls({ online, pendingCount, syncing, onSync, eventsConnected, eventsAvailable }: Props) {
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
          {eventsAvailable && (
            <p className="muted-text subtle">
              Flux d'événements : {eventsConnected ? "connecté" : "déconnecté"}
            </p>
          )}
        </div>
      </div>
      <button
        type="button"
        className="sync-button"
        onClick={() => void onSync()}
        disabled={!online || !hasPending || syncing}
      >
        {syncing ? "Synchronisation…" : "Synchroniser maintenant"}
      </button>
    </section>
  );
}
