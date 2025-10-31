import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CloudUpload, File as FileIcon, FileText, Image as ImageIcon } from "lucide-react";

import { toFriendlyError } from "../utils/errors";
import { useBatchesStore } from "../state/useBatchesStore";

type Props = {
  onUpload: (files: File[]) => Promise<string>;
  isUploading: boolean;
  online: boolean;
};

type PreviewStatus = "ready" | "uploading" | "success" | "error";

type PreviewItem = {
  id: string;
  file: File;
  url?: string;
  status: PreviewStatus;
  progress: number;
  batchId?: string;
};

export function UploadPanel({ onUpload, isUploading, online }: Props) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previews, setPreviews] = useState<PreviewItem[]>([]);
  const timersRef = useRef<Record<string, number>>({});
  const batches = useBatchesStore((state) => state.batches);

  const acceptedFormats = useMemo(() => ["Images (PNG, JPG)", "DOCX", "PDF", "TXT"].join(" • "), []);

  useEffect(() => {
    return () => {
      clearAllTimers();
      previews.forEach((preview) => preview.url && URL.revokeObjectURL(preview.url));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFiles = async (filesList: FileList | File[]) => {
    const files = Array.from(filesList);
    if (!files.length) {
      return;
    }

    setError(null);

    const timestamp = Date.now();
    const previewIds: string[] = [];
    const nextPreviews: PreviewItem[] = files.map((file, index) => {
      const id = `${timestamp}-${index}-${file.name}`;
      previewIds.push(id);
      return {
        id,
        file,
        url: file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined,
        status: "uploading",
        progress: 0
      };
    });

    appendPreviews(nextPreviews);
    startProgress(previewIds);

    try {
      const batchId = await onUpload(files);
      setPreviews((prev) =>
        prev.map((preview) =>
          previewIds.includes(preview.id)
            ? {
                ...preview,
                batchId
              }
            : preview
        )
      );
      if (!online) {
        previewIds.forEach((previewId) => finalizePreview(previewId, "success"));
      }
    } catch (err) {
      const friendly = toFriendlyError((err as Error)?.message);
      setError(friendly);
      previewIds.forEach((previewId) => finalizePreview(previewId, "error"));
    }
  };

  const appendPreviews = (items: PreviewItem[]) => {
    setPreviews((prev) => [...items, ...prev]);
  };

  const startProgress = useCallback((ids: string[]) => {
    ids.forEach((id) => {
      timersRef.current[id] = window.setInterval(() => {
        setPreviews((prev) =>
          prev.map((preview) =>
            preview.id === id && preview.status === "uploading"
              ? { ...preview, progress: Math.min(preview.progress + 8, 92) }
              : preview
          )
        );
      }, 200);
    });
  }, []);

  const finalizePreview = useCallback((id: string, status: PreviewStatus) => {
    const timer = timersRef.current[id];
    if (timer) {
      clearInterval(timer);
      delete timersRef.current[id];
    }
    setPreviews((prev) =>
      prev.map((preview) =>
        preview.id === id
          ? {
              ...preview,
              status,
              progress: status === "success" ? 100 : Math.max(preview.progress, 95)
            }
          : preview
      )
    );
  }, []);

  useEffect(() => {
    previews.forEach((preview) => {
      if (preview.status !== "uploading" || !preview.batchId) {
        return;
      }
      const batch = batches.find((item) => item.id === preview.batchId);
      if (!batch) {
        return;
      }
      if (batch.status === "failed") {
        finalizePreview(preview.id, "error");
        return;
      }
      const hasIngestionEvent = (batch.timeline ?? []).some((event) => event.stage === "ingestion:received");
      if (hasIngestionEvent || batch.status === "completed") {
        finalizePreview(preview.id, "success");
      }
    });
  }, [batches, previews, finalizePreview]);

  const clearAllTimers = () => {
    Object.values(timersRef.current).forEach((timer) => clearInterval(timer));
    timersRef.current = {};
  };

  const clearPreviews = () => {
    clearAllTimers();
    setPreviews((prev) => {
      prev.forEach((preview) => preview.url && URL.revokeObjectURL(preview.url));
      return [];
    });
    setError(null);
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
    <>
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
          <div className="dropzone-inner">
            <CloudUpload className="dropzone-icon" size={54} strokeWidth={1.8} />
            <div className="dropzone-copy">
              <strong>Glissez vos fichiers ici</strong>
              <span>ou</span>
            </div>
            <button type="button" onClick={handleBrowse} disabled={isUploading}>
              sélectionner des fichiers
            </button>
            <p className="hint">Formats acceptés : {acceptedFormats}</p>
            <ConnectionHint online={online} isUploading={isUploading} />
            {error && <p className="error">{error}</p>}
          </div>
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
        </div>
      </section>
      {previews.length > 0 && (
        <div className="preview-wrapper">
          <div className="preview-header">
            <p className="muted-text subtle">Fichiers sélectionnés (session en cours)</p>
            <button type="button" className="pill-button" onClick={clearPreviews}>
              Effacer
            </button>
          </div>
          <ul className="preview-list">
            {previews.map((preview) => (
              <li key={preview.id} className={`preview-item status-${preview.status}`}>
                {preview.url ? <img src={preview.url} alt={preview.file.name} /> : renderFileIcon(preview.file)}
                <div className="preview-info">
                  <p className="preview-name">{preview.file.name}</p>
                  <p className="muted-text subtle">{formatSize(preview.file.size)}</p>
                  <ProgressBar progress={preview.progress} status={preview.status} />
                </div>
                <span className={`preview-status status-${preview.status}`}>{renderStatusLabel(preview.status)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

function ConnectionHint({ online, isUploading }: { online: boolean; isUploading: boolean }) {
  if (!online) {
    return <p className="hint">Hors-ligne : les fichiers seront synchronisés dès le retour réseau.</p>;
  }
  if (isUploading) {
    return <p className="hint">Transfert en cours…</p>;
  }
  return <p className="hint">Glissez vos fichiers ou utilisez le bouton ci-dessus.</p>;
}

function ProgressBar({ progress, status }: { progress: number; status: PreviewStatus }) {
  return (
    <div className="progress-track">
      <div className={`progress-bar status-${status}`} style={{ width: `${progress}%` }} />
    </div>
  );
}

function renderFileIcon(file: File) {
  if (file.type === "application/pdf") {
    return <FileText className="file-icon" size={40} strokeWidth={1.8} />;
  }
  if (file.type.startsWith("image/")) {
    return <ImageIcon className="file-icon" size={40} strokeWidth={1.8} />;
  }
  return <FileIcon className="file-icon" size={40} strokeWidth={1.8} />;
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

function renderStatusLabel(status: PreviewStatus) {
  switch (status) {
    case "uploading":
      return "Envoi…";
    case "success":
      return "Transmis";
    case "error":
      return "Échec";
    default:
      return "Prêt";
  }
}
