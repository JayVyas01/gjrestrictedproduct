import { apiGet, query } from "./client";
import type { LicenceCard, LicenceDetail, LicenceRegister, LicenceStatus, StockRow } from "./types";

export interface RegisterFilters {
  number?: string;
  /** The backend searches by GSTIN only through this GET query (an exact match). */
  gstin?: string;
  status?: LicenceStatus | "";
  area?: number;
  page?: number;
}

export function myLicences(): Promise<LicenceCard[]> {
  return apiGet<LicenceCard[]>("/api/licences/mine");
}

export function myStock(): Promise<StockRow[]> {
  return apiGet<StockRow[]>("/api/stock/mine");
}

export function searchRegister(filters: RegisterFilters = {}): Promise<LicenceRegister> {
  return apiGet<LicenceRegister>(`/api/licences${query({ ...filters })}`);
}

export function getLicence(id: number): Promise<LicenceDetail> {
  return apiGet<LicenceDetail>(`/api/licences/${id}`);
}
