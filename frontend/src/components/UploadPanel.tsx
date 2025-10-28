import { useEffect, useMemo, useRef, useState } from "react";

import { toFriendlyError } from "../utils/errors";

type Props = {
  onUpload: (files: File[]) => Promise<void>;
  isUploading: boolean;
  online: boolean;
};

export function UploadPanel({ onUpload, isUploading, online }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  type PreviewItem = {
    id: string;
    file: File;
    url?: string;
    status: "ready" | "uploading" | "success" | "error";
  };

  const [previews, setPreviews] = useState<PreviewItem[]>([]);

  useEffect(() => {
    return () => {
      previews.forEach((preview) => preview.url && URL.revokeObjectURL(preview.url));
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
        url: file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined,
        status: "ready"
      }));
    });
    try {
      setPreviews((prev) => prev.map((preview) => ({ ...preview, status: "uploading" })));
      await onUpload(files);
      setPreviews((prev) => prev.map((preview) => ({ ...preview, status: "success" })));
    } catch (err) {
      setPreviews((prev) => prev.map((preview) => ({ ...preview, status: "error" })));
      const friendly = toFriendlyError((err as Error)?.message);
      setError(friendly);
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

  const clearPreviews = () => {
    setPreviews((prev) => {
      prev.forEach((preview) => preview.url && URL.revokeObjectURL(preview.url));
      return [];
    });
    setError(null);
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
        <div className="preview-wrapper">
          <div className="preview-header">
            <p className="muted-text subtle">Fichiers sélectionnés</p>
            <button type="button" className="link-button" onClick={clearPreviews}>
              Effacer
            </button>
          </div>
          <ul className="preview-list">
            {previews.map((preview) => (
              <li key={preview.id} className={`preview-item status-${preview.status}`}>
                {preview.url ? <img src={preview.url} alt={preview.file.name} /> : <span className="file-icon" />}
                <div>
                  <p>{preview.file.name}</p>
                  <p className="muted-text subtle">{formatSize(preview.file.size)}</p>
                </div>
                <span className="preview-status">{renderStatusLabel(preview.status)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function clearPreviews() {
  // noop placeholder replaced during component scope
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

function renderStatusLabel(status: "ready" | "uploading" | "success" | "error") {
  switch (status) {
    case "uploading":
      return "Envoi…";
    case "success":
      return "Transmis";
    case "error":
      return "Erreur";
    default:
      return "Prêt";
  }
}
