import { apiGet, apiPost, query } from "./client";
import type { LicenceCard, LicenceDetail, LicenceRegister, LicenceStatus, StockRow } from "./types";

/** The register's filters. They hold no personal data, so they may go in a query string. */
export interface RegisterFilters {
  status?: LicenceStatus | "";
  area?: number;
  page?: number;
}

/**
 * An exact search value: a licence number or a GSTIN. It only ever travels in a POST body,
 * never in a URL (a URL ends up in server and proxy logs, and in the browser history).
 */
export interface RegisterSearch {
  number?: string;
  gstin?: string;
}

export function myLicences(): Promise<LicenceCard[]> {
  return apiGet<LicenceCard[]>("/api/licences/mine");
}

export function myStock(): Promise<StockRow[]> {
  return apiGet<StockRow[]>("/api/stock/mine");
}

/** One page of the register: an exact search goes by POST, a plain listing by GET. */
export function searchRegister(
  filters: RegisterFilters = {},
  search: RegisterSearch = {},
): Promise<LicenceRegister> {
  const number = search.number?.trim();
  const gstin = search.gstin?.trim();
  if (number || gstin) {
    const body = { ...filters, ...(number ? { number } : {}), ...(gstin ? { gstin } : {}) };
    if (!body.status) delete body.status;
    return apiPost<LicenceRegister>("/api/licences/search", body);
  }
  return apiGet<LicenceRegister>(`/api/licences${query({ ...filters })}`);
}

export function getLicence(id: number): Promise<LicenceDetail> {
  return apiGet<LicenceDetail>(`/api/licences/${id}`);
}
