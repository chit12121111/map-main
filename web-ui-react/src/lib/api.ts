import type {
  CheckinsResponse,
  DiscoveredUrl,
  Email,
  PagedResponse,
  Place,
  PipelineRun,
  PipelineRunLogsResponse,
  PipelineRunsResponse,
  PipelineStatus,
  ResponsesResponse,
  Stats,
  TokensResponse,
  UiPreferenceResponse,
  EmailCampaignDetailResponse,
  EmailCampaignListResponse,
  EmailCampaignPreviewResponse,
} from "../types/api";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "http://127.0.0.1:8000";

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
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    if (ct.includes("application/json")) {
      let parsed: { message?: string; error?: string } | null = null;
      try {
        parsed = JSON.parse(text) as { message?: string; error?: string };
      } catch {
        // Fall through to plain-text normalization if JSON parsing fails.
      }
      if (parsed?.message) throw new Error(parsed.message);
      if (parsed?.error) throw new Error(parsed.error);
    }
    const cleaned = text.trim();
    if (!cleaned || cleaned.startsWith("<!DOCTYPE") || cleaned.startsWith("<html")) {
      throw new Error(`HTTP ${res.status}: ${res.statusText || "Request failed"}`);
    }
    throw new Error(cleaned.slice(0, 240));
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<{ status: string; message?: string; timestamp?: string }>("/health"),
  getStats: () => req<Stats>("/api/stats"),
  getPlaces: (
    filters?:
      | string
      | {
          status?: string;
          province?: string;
          district?: string;
          category?: string;
          normalizedCategory?: string;
          page?: number;
          perPage?: number;
        },
  ) => {
    const params = new URLSearchParams();
    params.set("per_page", String(typeof filters === "object" && filters?.perPage ? filters.perPage : 2000));
    if (typeof filters === "string") {
      if (filters) params.set("status", filters);
    } else if (filters) {
      if (filters.status) params.set("status", filters.status);
      if (filters.province) params.set("province", filters.province);
      if (filters.district) params.set("district", filters.district);
      if (filters.category) params.set("category", filters.category);
      if (filters.normalizedCategory) params.set("normalized_category", filters.normalizedCategory);
      if (filters.page) params.set("page", String(filters.page));
    }
    return req<PagedResponse<Place>>(`/api/places?${params.toString()}`);
  },
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
  }) => req<{ ok: boolean; run_id?: number; output: string[]; report_path?: string; elapsed_ms?: number; rows?: number }>(
    "/api/pipeline/run",
    {
    method: "POST",
    body: JSON.stringify(payload),
    },
  ),
  getPipelineStatus: () => req<PipelineStatus>("/api/pipeline/status"),
  getPipelineRuns: (limit = 50) => req<PipelineRunsResponse>(`/api/pipeline/runs?limit=${encodeURIComponent(String(limit))}`),
  getPipelineRun: (id: number) => req<PipelineRun>(`/api/pipeline/runs/${id}`),
  getPipelineRunLogs: (id: number, opts?: { sinceSeq?: number; limit?: number }) => {
    const params = new URLSearchParams();
    if (opts?.sinceSeq) params.set("since_seq", String(opts.sinceSeq));
    if (opts?.limit) params.set("limit", String(opts.limit));
    return req<PipelineRunLogsResponse>(`/api/pipeline/runs/${id}/logs${params.toString() ? `?${params.toString()}` : ""}`);
  },
  getUiPreference: (key: string, scope = "global") =>
    req<UiPreferenceResponse>(`/api/ui-preferences/${encodeURIComponent(key)}?scope=${encodeURIComponent(scope)}`),
  putUiPreference: (key: string, value: Record<string, unknown>, scope = "global") =>
    req<UiPreferenceResponse>(`/api/ui-preferences/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ scope, value }),
    }),
  previewEmailCampaign: (payload: {
    status?: string;
    province?: string;
    district?: string;
    category?: string;
    normalized_category?: string;
    source?: string;
    limit?: number;
    selected_emails?: string[];
  }) =>
    req<EmailCampaignPreviewResponse>("/api/email-campaigns/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  sendEmailCampaign: (payload: {
    subject: string;
    body_text: string;
    status?: string;
    province?: string;
    district?: string;
    category?: string;
    normalized_category?: string;
    source?: string;
    limit?: number;
    selected_emails?: string[];
    dry_run?: boolean;
  }) =>
    req<{ message: string; campaign_id?: number; count: number; dry_run?: boolean; recipients?: Array<{ email: string; place_id: string; source: string }> }>(
      "/api/email-campaigns/send",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  getEmailCampaigns: (limit = 30) =>
    req<EmailCampaignListResponse>(`/api/email-campaigns?limit=${encodeURIComponent(String(limit))}`),
  getEmailCampaign: (id: number) =>
    req<EmailCampaignDetailResponse>(`/api/email-campaigns/${id}`),
};

export { API_BASE_URL };

