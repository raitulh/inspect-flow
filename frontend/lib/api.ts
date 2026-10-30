export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type Site = { id: string; name: string; code: string; location?: string | null };
export type Station = {
  id: string; site_id: string; name: string; code: string; description?: string | null;
  expected_cycle_seconds?: number | null; is_active: boolean;
};
export type Camera = { id: string; station_id: string; name: string; source_type: string; status: string; last_error?: string | null };
export type Job = {
  id: string; station_id: string; video_id: string; status: string; progress: number;
  provider_name: string; error_message?: string | null; result_summary?: string | null;
  created_at: string; completed_at?: string | null;
};
export type Event = {
  id: string; station_id: string; video_id: string | null; job_id: string | null; rule_id?: string | null;
  event_type: string; severity: string; status: string; summary: string; details_json: string;
  confidence?: number | null; timestamp_seconds: number; model_version: string;
  rule_version?: number | null;
  acknowledged_at?: string | null; resolved_at?: string | null; resolution_note?: string | null;
  false_positive_reason?: string | null; created_at: string;
};
export type Rule = {
  id: string; station_id: string; name: string; rule_type: string; config: Record<string, unknown>;
  severity: string; is_enabled: boolean; version: number; created_at: string;
};
export type Summary = {
  stations: number; cameras: number; online_cameras: number; total_events: number; open_events: number;
  queued_jobs: number; events_by_severity: Record<string, number>;
};
export type User = { id: string; email: string; role: string; organization_id: string };

function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const part = document.cookie.split(";").map((v) => v.trim()).find((v) => v.startsWith("lg_csrf="));
  return part ? decodeURIComponent(part.slice("lg_csrf=".length)) : undefined;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrf = csrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init, method, headers, credentials: "include", cache: "no-store",
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json() as { detail?: string };
      if (body.detail) message = body.detail;
    } catch { /* Keep generic status when the response is not JSON. */ }
    if (response.status === 401 && typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleString();
}

export function prettyLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}
