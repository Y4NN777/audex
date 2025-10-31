import { api, API_BASE_URL } from "./api";
import { mergeBatchRecord } from "./db";
import { resolveReportUrl } from "./reports";
import type {
  BatchSummary,
  BatchTimelineEntry,
  Observation,
  OCRText,
  ReportInsights,
  RiskBreakdown,
  RiskScore,
  StoredFile
} from "../types/batch";
import { useBatchesStore } from "../state/useBatchesStore";

type ServerFileMetadata = {
  filename: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256: string;
  stored_path: string;
  metadata?: Record<string, unknown> | null;
};

type ServerTimeline = {
  code: string;
  label: string;
  kind: string;
  timestamp: string;
  progress?: number | null;
  details?: Record<string, unknown> | null;
};

type ServerObservation = {
  filename: string;
  label: string;
  severity: string;
  confidence?: number | null;
  bbox?: number[] | null;
  source?: string | null;
  class_name?: string | null;
  extra?: Record<string, unknown> | null;
  created_at?: string | null;
};

type ServerOCRText = {
  filename: string;
  engine: string;
  content: string;
  confidence?: number | null;
  warnings?: string[] | null;
  error?: string | null;
};

type ServerRiskBreakdown = {
  label: string;
  severity: string;
  count: number;
  score: number;
};

type ServerRiskScore = {
  total_score: number;
  normalized_score: number;
  breakdown: ServerRiskBreakdown[] | null;
  created_at?: string;
};

type ServerReportSummary = {
  status: string;
  source?: string | null;
  text?: string | null;
  findings?: string[] | null;
  recommendations?: string[] | null;
  warnings?: string[] | null;
  prompt_hash?: string | null;
  response_hash?: string | null;
  duration_ms?: number | null;
  created_at?: string | null;
};

type ServerBatchResponse = {
  batch_id: string;
  stored_at: string;
  status: string;
  report_hash?: string | null;
  report_url?: string | null;
  last_error?: string | null;
  files: ServerFileMetadata[];
  timeline?: ServerTimeline[] | null;
  observations?: ServerObservation[] | null;
  ocr_texts?: ServerOCRText[] | null;
  gemini_status?: string | null;
  gemini_summary?: string | null;
  gemini_prompt_hash?: string | null;
  gemini_model?: string | null;
  risk_score?: ServerRiskScore | null;
  summary?: ServerReportSummary | null;
};

function mapFiles(files: ServerFileMetadata[], batchId: string): StoredFile[] {
  return files.map((file, index) => ({
    id: `${batchId}-server-${index}-${file.filename}`,
    name: file.filename,
    size: file.size_bytes,
    type: file.content_type,
    lastModified: Date.now(),
    checksum: file.checksum_sha256,
    storedPath: file.stored_path,
    metadata: file.metadata ?? undefined
  }));
}

function mapTimeline(batchId: string, timeline?: ServerTimeline[] | null): BatchTimelineEntry[] {
  if (!timeline) {
    return [];
  }
  return timeline.map((event) => ({
    id: `${batchId}-${event.code}-${event.timestamp}`,
    stage: event.code,
    label: event.label,
    timestamp: event.timestamp,
    kind: (event.kind as BatchTimelineEntry["kind"]) ?? "info",
    details: event.details ?? undefined,
    progress: typeof event.progress === "number" ? event.progress : undefined
  }));
}

function mapRiskScore(score?: ServerRiskScore | null): RiskScore | undefined {
  if (!score) {
    return undefined;
  }
  const breakdown: RiskBreakdown[] = Array.isArray(score.breakdown)
    ? score.breakdown.map((item) => ({
        label: item.label,
        severity: item.severity,
        count: item.count,
        score: item.score
      }))
    : [];
  return {
    totalScore: score.total_score,
    normalizedScore: score.normalized_score,
    breakdown,
    createdAt: score.created_at
  };
}

function mapSummary(summary?: ServerReportSummary | null) {
  if (!summary) {
    return undefined;
  }
  return {
    status: summary.status,
    source: summary.source,
    text: summary.text,
    findings: summary.findings ?? undefined,
    recommendations: summary.recommendations ?? undefined,
    warnings: summary.warnings ?? undefined,
    promptHash: summary.prompt_hash,
    responseHash: summary.response_hash,
    durationMs: summary.duration_ms,
    createdAt: summary.created_at
  };
}

function mapObservations(observations?: ServerObservation[] | null): Observation[] | undefined {
  if (!observations) {
    return undefined;
  }
  return observations.map((obs) => ({
    filename: obs.filename,
    label: obs.label,
    severity: obs.severity,
    confidence: obs.confidence ?? undefined,
    bbox: obs.bbox ?? undefined,
    source: obs.source ?? undefined,
    className: obs.class_name ?? undefined,
    extra: obs.extra ?? undefined,
    createdAt: obs.created_at ?? undefined
  }));
}

function mapOcrTexts(ocrTexts?: ServerOCRText[] | null): OCRText[] | undefined {
  if (!ocrTexts) {
    return undefined;
  }
  return ocrTexts.map((item) => ({
    filename: item.filename,
    engine: item.engine,
    content: item.content,
    confidence: item.confidence ?? undefined,
    warnings: item.warnings ?? undefined,
    error: item.error ?? undefined
  }));
}

function computeProgress(entries: BatchTimelineEntry[]): number {
  if (!entries.length) {
    return 0;
  }
  return entries.reduce((max, entry) => (entry.progress !== undefined ? Math.max(max, entry.progress) : max), 0);
}

export function mapServerBatch(response: ServerBatchResponse): BatchSummary {
  const timeline = mapTimeline(response.batch_id, response.timeline);
  const files = mapFiles(response.files ?? [], response.batch_id);
  const risk = mapRiskScore(response.risk_score);
  const summary = mapSummary(response.summary);
  const observations = mapObservations(response.observations);
  const ocrTexts = mapOcrTexts(response.ocr_texts);
  const insights: ReportInsights | undefined =
    risk || summary || response.gemini_status || response.gemini_summary || response.gemini_model || response.gemini_prompt_hash
      ? {
          geminiStatus: response.gemini_status ?? undefined,
          geminiSummary: response.gemini_summary ?? undefined,
          geminiModel: response.gemini_model ?? undefined,
          geminiPromptHash: response.gemini_prompt_hash ?? undefined,
          risk,
          summary,
          syncedAt: new Date().toISOString()
        }
      : undefined;

  const reportUrl = response.report_url ? new URL(response.report_url, API_BASE_URL).toString() : resolveReportUrl(response.batch_id);

  return {
    id: response.batch_id,
    createdAt: response.stored_at,
    status: response.status as BatchSummary["status"],
    files,
    timeline,
    progress: computeProgress(timeline),
    lastError: response.last_error ?? undefined,
    report: response.report_hash
      ? {
          hash: response.report_hash,
          downloadUrl: reportUrl,
          generatedAt: response.stored_at
        }
      : undefined,
    insights,
    observations,
    ocrTexts,
    syncedAt: new Date().toISOString()
  };
}

export async function fetchBatchDetails(batchId: string): Promise<BatchSummary> {
  const response = await api.get<ServerBatchResponse>(`/ingestion/batches/${batchId}`);
  return mapServerBatch(response.data);
}

export async function syncBatchFromServer(batchId: string): Promise<BatchSummary | undefined> {
  try {
    const serverBatch = await fetchBatchDetails(batchId);
    const store = useBatchesStore.getState();
    const current = store.batches.find((batch) => batch.id === batchId);
    const combinedTimeline = mergeTimelines(current?.timeline ?? [], serverBatch.timeline);
    const mergedFiles = mergeFiles(current?.files ?? [], serverBatch.files);

    const merged: BatchSummary = {
      ...serverBatch,
      files: mergedFiles,
      timeline: combinedTimeline,
      progress: Math.max(serverBatch.progress, current?.progress ?? 0),
      status: serverBatch.status ?? current?.status ?? "processing",
      lastError: serverBatch.lastError ?? current?.lastError,
      report: serverBatch.report ?? current?.report,
      insights: mergeInsights(current?.insights, serverBatch.insights),
      observations: serverBatch.observations ?? current?.observations,
      ocrTexts: serverBatch.ocrTexts ?? current?.ocrTexts,
      syncedAt: new Date().toISOString()
    };

    if (current) {
      store.mergeBatch(batchId, merged);
      await mergeBatchRecord(batchId, merged);
    } else {
      store.upsertBatch(merged);
      await mergeBatchRecord(batchId, merged);
    }
    return merged;
  } catch (error) {
    console.error(`Failed to fetch batch ${batchId}`, error);
    return undefined;
  }
}

function mergeTimelines(current: BatchTimelineEntry[], incoming: BatchTimelineEntry[]): BatchTimelineEntry[] {
  const map = new Map<string, BatchTimelineEntry>();
  for (const entry of current) {
    map.set(entry.id, entry);
  }
  for (const entry of incoming) {
    map.set(entry.id, entry);
  }
  return Array.from(map.values()).sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

function mergeFiles(current: StoredFile[], incoming: StoredFile[]): StoredFile[] {
  const map = new Map<string, StoredFile>();
  for (const file of current) {
    map.set(file.name, file);
  }
  for (const file of incoming) {
    const existing = map.get(file.name);
    map.set(file.name, { ...(existing ?? {}), ...file });
  }
  return Array.from(map.values());
}

function mergeInsights(current?: ReportInsights, incoming?: ReportInsights): ReportInsights | undefined {
  if (!current && !incoming) {
    return undefined;
  }
  return {
    geminiStatus: incoming?.geminiStatus ?? current?.geminiStatus,
    geminiSummary: incoming?.geminiSummary ?? current?.geminiSummary,
    geminiModel: incoming?.geminiModel ?? current?.geminiModel,
    geminiPromptHash: incoming?.geminiPromptHash ?? current?.geminiPromptHash,
    risk: incoming?.risk ?? current?.risk,
    summary: incoming?.summary ?? current?.summary,
    syncedAt: incoming?.syncedAt ?? current?.syncedAt ?? new Date().toISOString()
  };
}
