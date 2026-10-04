import { apiGet, apiPost, query } from "./client";
import type {
  BuyerFound,
  Challenge,
  CheckResult,
  Outcome,
  TransactionDetail,
  TransactionSummary,
} from "./types";

export interface TransactionFilters {
  awaiting?: "me" | "";
  side?: "sales" | "purchases" | "";
  approved_by?: "superintendent" | "";
}

/** A sale to check. The GSTIN only ever travels in a POST body, never in a URL. */
export interface SaleCheck {
  buyer_gstin: string;
  substance_code: string;
  quantity: string;
}

export interface NewSale extends SaleCheck {
  transporter_name: string;
  transporter_id_number: string;
  vehicle_number: string;
  route: string;
}

export interface Decision {
  challenge_id: string;
  code: string;
  outcome: Outcome;
  reason_code?: string;
  comment?: string;
}

const base = (reference: string) => `/api/transactions/${encodeURIComponent(reference)}`;

export function listTransactions(filters: TransactionFilters = {}): Promise<TransactionSummary[]> {
  return apiGet<TransactionSummary[]>(`/api/transactions${query({ ...filters })}`);
}

export function getTransaction(reference: string): Promise<TransactionDetail> {
  return apiGet<TransactionDetail>(base(reference));
}

export function checkSale(sale: SaleCheck): Promise<CheckResult> {
  return apiPost<CheckResult>("/api/transactions/check", sale);
}

export function lookupBuyer(gstin: string): Promise<BuyerFound> {
  return apiPost<BuyerFound>("/api/transactions/buyer-lookup", { gstin });
}

export function startSale(sale: NewSale): Promise<TransactionDetail> {
  return apiPost<TransactionDetail>("/api/transactions", sale);
}

export function requestDecisionCode(reference: string): Promise<Challenge> {
  return apiPost<Challenge>(`${base(reference)}/decision-code`);
}

export function decideTransaction(
  reference: string,
  decision: Decision,
): Promise<TransactionDetail> {
  return apiPost<TransactionDetail>(`${base(reference)}/decide`, decision);
}

export function cancelTransaction(reference: string): Promise<TransactionDetail> {
  return apiPost<TransactionDetail>(`${base(reference)}/cancel`);
}
