import { apiGet, apiPost } from "./client";
import type { Alert, AlertList } from "./types";

export function listAlerts(): Promise<AlertList> {
  return apiGet<AlertList>("/api/alerts");
}

export function acknowledgeAlert(id: number, note = ""): Promise<Alert> {
  return apiPost<Alert>(`/api/alerts/${id}/acknowledge`, { note });
}
