import axios from "axios";

import { API_BASE_URL, parseApiError } from "./api";

export async function downloadReport(batchId: string, directUrl?: string, filename?: string): Promise<void> {
  try {
    const absoluteUrl = resolveAbsoluteReportUrl(directUrl ?? resolveReportPath(batchId));
    const response = await axios.get(absoluteUrl, {
      responseType: "blob",
      withCredentials: false
    });
    const blob = new Blob([response.data], {
      type: response.headers["content-type"] ?? "application/pdf"
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename ?? `audit-${batchId}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    const detail = parseApiError(error);
    throw new Error(detail.message);
  }
}

function resolveReportPath(batchId: string): string {
  return `/api/v1/ingestion/reports/${batchId}`;
}

function resolveAbsoluteReportUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  const trimmed = path.startsWith("/") ? path.slice(1) : path;
  return `${API_BASE_URL.replace(/\/$/, "")}/${trimmed}`;
}

export function resolveReportUrl(batchId: string): string {
  return resolveAbsoluteReportUrl(resolveReportPath(batchId));
}
