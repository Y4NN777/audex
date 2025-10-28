import { useMemo, useState } from "react";

type BatchStub = {
  id: string;
  status: "pending" | "processing" | "completed";
  files: number;
};

const demoBatches: BatchStub[] = [
  { id: "batch-001", status: "completed", files: 5 },
  { id: "batch-002", status: "processing", files: 3 }
];

function App() {
  const [batches] = useState(demoBatches);
  const completed = useMemo(() => batches.filter((batch) => batch.status === "completed").length, [batches]);

  return (
    <div className="app-shell">
      <header>
        <h1>AUDEX MVP Console</h1>
        <p>Uploader vos audits, suivez le pipeline IA et récupérez le rapport final.</p>
      </header>

      <section className="card">
        <h2>Lots récents</h2>
        <p>
          {completed} lot(s) complété(s) sur {batches.length}
        </p>
        <ul>
          {batches.map((batch) => (
            <li key={batch.id}>
              <span>{batch.id}</span>
              <span data-status={batch.status}>{batch.status}</span>
              <span>{batch.files} fichiers</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Prochaines étapes</h2>
        <ol>
          <li>Implémenter l’upload multi-fichiers avec reprise hors-ligne.</li>
          <li>Connecter l’API FastAPI `/api/v1/ingestion/batches`.</li>
          <li>Afficher les statuts en temps réel via WebSocket/EventSource.</li>
        </ol>
      </section>
    </div>
  );
}

export default App;
