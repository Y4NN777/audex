export type BatchStatus = "pending" | "uploading" | "processing" | "completed" | "failed";

export type TimelineEventKind = "info" | "success" | "warning" | "error";

export type BatchTimelineEntry = {
  id: string;
  stage: string;
  label: string;
  timestamp: string;
  kind: TimelineEventKind;
  details?: Record<string, unknown>;
  progress?: number;
};

export type ServerTimelineEvent = {
  eventId: string;
  code: string;
  label: string;
  kind?: TimelineEventKind;
  timestamp: string;
  details?: Record<string, unknown>;
  progress?: number;
};

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
  timeline: BatchTimelineEntry[];
  progress: number;
  lastError?: string;
  report?: ReportInfo;
};
