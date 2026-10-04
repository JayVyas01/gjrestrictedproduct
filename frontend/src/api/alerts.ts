import { apiGet, apiPost, type RequestOptions } from "./client";
import type { Alert, AlertList } from "./types";

export function listAlerts(options?: RequestOptions): Promise<AlertList> {
  return apiGet<AlertList>("/api/alerts", options);
}

export function acknowledgeAlert(id: number, note = ""): Promise<Alert> {
  return apiPost<Alert>(`/api/alerts/${id}/acknowledge`, { note });
}
