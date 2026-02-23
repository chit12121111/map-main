import type {
  CheckinsResponse,
  DiscoveredUrl,
  Email,
  PagedResponse,
  Place,
  PipelineStatus,
  ResponsesResponse,
  Stats,
  TokensResponse,
} from "../types/api";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<{ status: string; message?: string; timestamp?: string }>("/health"),
  getStats: () => req<Stats>("/api/stats"),
  getPlaces: (status?: string) =>
    req<PagedResponse<Place>>(`/api/places?per_page=2000${status ? `&status=${encodeURIComponent(status)}` : ""}`),
  getPlace: (id: string) => req<Place>(`/api/places/${encodeURIComponent(id)}`),
  updatePlace: (id: string, payload: Partial<Place>) =>
    req<Place>(`/api/places/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload) }),
  importPlaces: (places: unknown[]) => req<{ message: string; created: number; updated: number }>("/api/places/import", {
    method: "POST",
    body: JSON.stringify({ places }),
  }),
  clearAll: () => req<{ message: string }>("/api/places/clear", { method: "POST" }),
  getEmails: (opts?: { placeId?: string; source?: string; includePlace?: boolean }) => {
    const params = new URLSearchParams();
    params.set("per_page", "2000");
    if (opts?.placeId) params.set("place_id", opts.placeId);
    if (opts?.source) params.set("source", opts.source);
    if (opts?.includePlace) params.set("include_place", "1");
    return req<PagedResponse<Email>>(`/api/emails?${params.toString()}`);
  },
  updateEmail: (id: number, payload: Record<string, unknown>) =>
    req<Email>(`/api/emails/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  bulkDeleteEmails: (ids: number[]) =>
    req<{ message: string; deleted: number }>("/api/emails/bulk-delete", { method: "POST", body: JSON.stringify({ ids }) }),
  getDiscoveredUrls: (status?: string) =>
    req<PagedResponse<DiscoveredUrl>>(`/api/discovered-urls?per_page=1000${status ? `&status=${encodeURIComponent(status)}` : ""}`),
  getTokens: (email?: string) => req<TokensResponse>(`/api/tokens${email ? `?email=${encodeURIComponent(email)}` : ""}`),
  createToken: (email: string, expiresInDays?: number) =>
    req<{ token: string; link: string; email: string; expires_at?: string | null }>("/api/create-token", {
      method: "POST",
      body: JSON.stringify({ email, expires_in_days: expiresInDays }),
    }),
  getCheckins: (email?: string) => req<CheckinsResponse>(`/api/checkins${email ? `?email=${encodeURIComponent(email)}` : ""}`),
  getResponses: () => req<ResponsesResponse>("/api/responses"),
  runPipeline: (payload: {
    query: string;
    concurrency?: number;
    inactivity?: string;
    lang?: string;
    radius?: number;
    depth?: number;
  }) => req<{ ok: boolean; output: string[]; report_path?: string; elapsed_ms?: number; rows?: number }>("/api/pipeline/run", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  getPipelineStatus: () => req<PipelineStatus>("/api/pipeline/status"),
};

export { API_BASE_URL };

