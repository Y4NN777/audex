import axios from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const resolvedTimeout = (() => {
  const raw = import.meta.env.VITE_API_TIMEOUT_MS;
  if (raw) {
    const parsed = Number(raw);
    if (Number.isFinite(parsed) && parsed >= 0) {
      return parsed;
    }
  }
  // 0 disables the Axios timeout constraint to support long-running pipeline requests.
  return 0;
})();

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: resolvedTimeout,
  headers: {
    "X-Client": "audex-frontend"
  }
});

export type ApiError = {
  message: string;
  status?: number;
};

export function parseApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const message =
      typeof error.response?.data === "string"
        ? error.response.data
        : error.code === "ECONNABORTED"
        ? "Temps de réponse dépassé"
        : error.message;
    return { message, status };
  }
  return { message: (error as Error)?.message ?? "Erreur inattendue" };
}
