import axios from "axios";

function csrfCookie(): string {
  const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export const api = axios.create({ baseURL: "/api/v1", withCredentials: true });

api.interceptors.request.use((config) => {
  const method = (config.method || "get").toLowerCase();
  if (!["get", "head", "options"].includes(method)) config.headers["X-CSRFToken"] = csrfCookie();
  return config;
});

export async function ensureCsrf() {
  await api.get("/auth/csrf/");
}

/** Turn any DRF error body into one readable line. */
export function errorMessage(err: unknown): string {
  const e = err as { response?: { data?: unknown; status?: number }; message?: string };
  const d = e.response?.data;
  if (typeof d === "string") return d.slice(0, 200);
  if (d && typeof d === "object") {
    const obj = d as Record<string, unknown>;
    if (typeof obj.detail === "string") return obj.detail;
    return Object.entries(obj)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : String(v)}`)
      .join(" | ");
  }
  return e.message || "Something went wrong";
}

export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
