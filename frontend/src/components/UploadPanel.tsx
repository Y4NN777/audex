import { useEffect, useMemo, useRef, useState } from "react";

type Props = {
  onUpload: (files: File[]) => Promise<void>;
  isUploading: boolean;
  online: boolean;
};

export function UploadPanel({ onUpload, isUploading, online }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previews, setPreviews] = useState<Array<{ id: string; file: File; url?: string }>>([]);

  useEffect(() => {
    return () => {
      previews.forEach((preview) => {
        if (preview.url) {
          URL.revokeObjectURL(preview.url);
        }
      });
    };
  }, [previews]);

  const acceptedFormats = useMemo(() => ["images", "PDF", "TXT"].join(" • "), []);

  const handleFiles = async (filesList: FileList | File[]) => {
    const files = Array.from(filesList);
    if (!files.length) {
      return;
    }
    setError(null);
    setPreviews((prev) => {
      prev.forEach((preview) => preview.url && URL.revokeObjectURL(preview.url));
      return files.map((file) => ({
        id: `${file.lastModified}-${file.name}`,
        file,
        url: file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined
      }));
    });
    try {
      await onUpload(files);
      setPreviews([]);
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
        <p className="hint">Formats acceptés : {acceptedFormats}</p>
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
      {previews.length > 0 && (
        <ul className="preview-list">
          {previews.map((preview) => (
            <li key={preview.id} className="preview-item">
              {preview.url ? <img src={preview.url} alt={preview.file.name} /> : <span className="file-icon" />}
              <div>
                <p>{preview.file.name}</p>
                <p className="muted-text subtle">{formatSize(preview.file.size)}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} o`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} Ko`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}
