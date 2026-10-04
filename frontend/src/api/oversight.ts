import { apiGet, apiPost, apiPut } from "./client";
import type { BatchDetail, BatchSummary, Challenge, ReviewSetting } from "./types";

export interface Flag {
  reference: string;
  reason_code: string;
  comment?: string;
}

export interface ReviewPeriod {
  period_days: number;
  starts_on?: string | null;
}

const batch = (id: number) => `/api/oversight/batches/${id}`;

export function listBatches(): Promise<BatchSummary[]> {
  return apiGet<BatchSummary[]>("/api/oversight/batches");
}

export function getBatch(id: number): Promise<BatchDetail> {
  return apiGet<BatchDetail>(batch(id));
}

export function flagItem(id: number, flag: Flag): Promise<BatchDetail> {
  return apiPost<BatchDetail>(`${batch(id)}/flag`, flag);
}

export function requestSignOffCode(id: number): Promise<Challenge> {
  return apiPost<Challenge>(`${batch(id)}/sign-off-code`);
}

export function signOff(id: number, challengeId: string, code: string): Promise<BatchDetail> {
  return apiPost<BatchDetail>(`${batch(id)}/sign-off`, { challenge_id: challengeId, code });
}

export function listReviewSettings(): Promise<ReviewSetting[]> {
  return apiGet<ReviewSetting[]>("/api/oversight/review-settings");
}

export function saveReviewSetting(
  positionId: number,
  period: ReviewPeriod,
): Promise<ReviewSetting> {
  return apiPut<ReviewSetting>(`/api/oversight/review-settings/${positionId}`, period);
}
