import { apiGet } from "./client";
import type {
  ApprovalThreshold,
  LicenceType,
  ReasonCode,
  ReasonKind,
  Substance,
  SubstanceClass,
} from "./types";

export function listSubstances(): Promise<Substance[]> {
  return apiGet<Substance[]>("/api/catalogue/substances");
}

export function listClasses(): Promise<SubstanceClass[]> {
  return apiGet<SubstanceClass[]>("/api/catalogue/classes");
}

export function listLicenceTypes(): Promise<LicenceType[]> {
  return apiGet<LicenceType[]>("/api/catalogue/licence-types");
}

export function listApprovalThresholds(): Promise<ApprovalThreshold[]> {
  return apiGet<ApprovalThreshold[]>("/api/catalogue/approval-thresholds");
}

export function listReasonCodes(kind: ReasonKind): Promise<ReasonCode[]> {
  return apiGet<ReasonCode[]>(`/api/reason-codes?kind=${kind}`);
}
