export type Stats = {
  total_places: number;
  places_with_email: number;
  status_breakdown: Record<string, number>;
  total_emails: number;
  source_breakdown: Record<string, number>;
  total_discovered: number;
  discovered_breakdown: Record<string, number>;
  discovered_types: Record<string, number>;
};

export type Place = {
  place_id: string;
  name: string;
  website?: string | null;
  phone?: string | null;
  google_maps_url?: string | null;
  address?: string | null;
  category?: string | null;
  review_count?: number | null;
  review_rating?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  raw_data?: string | null;
  status?: string;
  province?: string | null;
  district?: string | null;
  normalized_category?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type Email = {
  id: number;
  place_id: string;
  email: string;
  source: string;
  created_at?: string;
  place?: Place | null;
};

export type DiscoveredUrl = {
  id: number;
  place_id: string;
  url: string;
  url_type: string;
  found_by_stage: string;
  status: string;
  created_at?: string;
};

export type PagedResponse<T> = {
  data: T[];
  total: number;
  per_page: number;
  current_page: number;
};

export type TokenItem = {
  token: string;
  email: string;
  used: boolean;
  used_at?: string | null;
  expires_at?: string | null;
  created_at?: string;
};

export type TokensResponse = {
  total: number;
  tokens: TokenItem[];
};

export type CheckinItem = {
  email: string;
  ip_address?: string | null;
  user_agent?: string | null;
  checked_in_at: string;
};

export type CheckinsResponse = {
  total: number;
  checkins: CheckinItem[];
};

export type ResponsesResponse = {
  total_interested: number;
  total_unsubscribed: number;
  interested: Array<{ email: string; response: string; created_at: string }>;
  unsubscribed: Array<{ email: string; response: string; created_at: string }>;
};

export type PipelineStatus = {
  run_id?: number | null;
  running: boolean;
  status?: string;
  started_at?: string | null;
  finished_at?: string | null;
  last_query?: string | null;
  ok?: boolean | null;
  rows?: number | null;
  elapsed_ms?: number | null;
  error?: string | null;
  report_path?: string | null;
  output: string[];
};

export type PipelineRun = {
  id: number;
  query: string;
  status: string;
  running: boolean;
  started_at?: string | null;
  finished_at?: string | null;
  elapsed_ms?: number | null;
  rows?: number | null;
  report_path?: string | null;
  error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PipelineRunsResponse = {
  total: number;
  runs: PipelineRun[];
};

export type PipelineRunLog = {
  seq: number;
  level: string;
  line: string;
  created_at?: string | null;
};

export type PipelineRunLogsResponse = {
  run_id: number;
  count: number;
  logs: PipelineRunLog[];
  last_seq: number;
};

export type UiPreferenceResponse = {
  key: string;
  scope: string;
  value: Record<string, unknown> | null;
};

export type EmailCampaign = {
  id: number;
  subject: string;
  body_text: string;
  filters_json?: Record<string, unknown> | null;
  status: string;
  requested_by?: string | null;
  total_recipients: number;
  pending_count: number;
  sent_count: number;
  failed_count: number;
  started_at?: string | null;
  finished_at?: string | null;
  last_error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type EmailCampaignOutboxItem = {
  id: number;
  email: string;
  place_id?: string | null;
  source?: string | null;
  token?: string | null;
  status: string;
  response_status?: "INTERESTED" | "UNSUBSCRIBED" | "PENDING";
  retry_count: number;
  last_error?: string | null;
  sent_at?: string | null;
  responded_at?: string | null;
  created_at?: string | null;
};

export type EmailCampaignPreviewResponse = {
  count: number;
  recipients: Array<{ email: string; place_id: string; source: string }>;
  filters: Record<string, unknown>;
  dry_run?: boolean;
};

export type EmailCampaignListResponse = {
  total: number;
  campaigns: EmailCampaign[];
};

export type EmailCampaignDetailResponse = {
  campaign: EmailCampaign;
  response_summary?: {
    INTERESTED: number;
    UNSUBSCRIBED: number;
    PENDING: number;
  };
  outbox: EmailCampaignOutboxItem[];
};

