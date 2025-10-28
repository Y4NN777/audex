import { useRef, useState } from "react";

type Props = {
  onUpload: (files: File[]) => Promise<void>;
  isUploading: boolean;
  online: boolean;
};

export function UploadPanel({ onUpload, isUploading, online }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFiles = async (filesList: FileList | File[]) => {
    const files = Array.from(filesList);
    if (!files.length) {
      return;
    }
    setError(null);
    try {
      await onUpload(files);
    } catch (err) {
      setError((err as Error).message ?? "Erreur lors de l'enregistrement des fichiers.");
    }
  };

  const handleDrop = async (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    await handleFiles(event.dataTransfer.files);
  };

  const handleBrowse = () => {
    inputRef.current?.click();
  };

  return (
    <section className={`upload-panel ${dragActive ? "dragging" : ""}`}>
      <div
        className="dropzone"
        onDragOver={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
      >
        <p>Déposez vos fichiers d'audit ici ou</p>
        <button type="button" onClick={handleBrowse} disabled={isUploading}>
          sélectionner des fichiers
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          onChange={(event) => {
            if (event.target.files) {
              void handleFiles(event.target.files);
              event.target.value = "";
            }
          }}
        />
        {!online && <p className="hint">Vous êtes hors-ligne : les lots seront envoyés automatiquement plus tard.</p>}
        {isUploading && <p className="hint">Envoi en cours…</p>}
        {error && <p className="error">{error}</p>}
      </div>
    </section>
  );
}
