import { api, API_BASE_URL, parseApiError } from "./api";

export async function downloadReport(batchId: string, directUrl?: string, filename?: string): Promise<void> {
  if (directUrl && directUrl.startsWith("http")) {
    const link = document.createElement("a");
    link.href = directUrl;
    link.target = "_blank";
    link.rel = "noopener";
    link.download = filename ?? `audit-${batchId}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    return;
  }

  try {
    const response = await api.get(directUrl ?? `/reports/${batchId}`, {
      responseType: "blob"
    });
    const blob = new Blob([response.data], { type: response.headers["content-type"] ?? "application/pdf" });
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

export function resolveReportUrl(batchId: string): string {
  return `${API_BASE_URL}/api/v1/reports/${batchId}`;
}
