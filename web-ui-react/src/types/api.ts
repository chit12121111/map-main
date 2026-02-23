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
  running: boolean;
  started_at?: string | null;
  finished_at?: string | null;
  last_query?: string | null;
  ok?: boolean | null;
  rows?: number | null;
  elapsed_ms?: number | null;
  report_path?: string | null;
  output: string[];
};

