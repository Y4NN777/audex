export type BatchStatus = "pending" | "uploading" | "processing" | "completed" | "failed";

export type StoredFile = {
  id: string;
  name: string;
  size: number;
  type: string;
  lastModified: number;
};

export type ReportInfo = {
  hash?: string;
  downloadUrl?: string;
};

export type BatchSummary = {
  id: string;
  createdAt: string;
  status: BatchStatus;
  files: StoredFile[];
  lastError?: string;
  report?: ReportInfo;
};
