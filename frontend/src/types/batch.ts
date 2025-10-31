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
  checksum?: string;
  storedPath?: string;
  metadata?: Record<string, unknown> | null;
};

export type ReportInfo = {
  hash?: string;
  downloadUrl?: string;
  generatedAt?: string;
};

export type RiskBreakdown = {
  label: string;
  severity: string;
  count: number;
  score: number;
};

export type RiskScore = {
  totalScore: number;
  normalizedScore: number;
  breakdown: RiskBreakdown[];
  createdAt?: string;
};

export type ReportSummary = {
  status: string;
  source?: string | null;
  text?: string | null;
  findings?: string[];
  recommendations?: string[];
  warnings?: string[];
  promptHash?: string | null;
  responseHash?: string | null;
  durationMs?: number | null;
  createdAt?: string | null;
};

export type ReportInsights = {
  geminiStatus?: string | null;
  geminiSummary?: string | null;
  geminiModel?: string | null;
  geminiPromptHash?: string | null;
  risk?: RiskScore;
  summary?: ReportSummary;
  syncedAt?: string;
};

export type OCRText = {
  filename: string;
  engine: string;
  content: string;
  confidence?: number | null;
  warnings?: string[] | null;
  error?: string | null;
};

export type Observation = {
  filename: string;
  label: string;
  severity: string;
  confidence?: number | null;
  bbox?: number[] | null;
  source?: string | null;
  className?: string | null;
  extra?: Record<string, unknown> | null;
  createdAt?: string | null;
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
  insights?: ReportInsights;
  observations?: Observation[];
  ocrTexts?: OCRText[];
  syncedAt?: string;
};
