import axios from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 15000,
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
    const message = typeof error.response?.data === "string" ? error.response.data : error.message;
    return { message, status };
  }
  return { message: (error as Error)?.message ?? "Erreur inattendue" };
}
