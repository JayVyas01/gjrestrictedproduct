import { useQuery } from "@tanstack/react-query";
import {
  listApprovalThresholds,
  listClasses,
  listLicenceTypes,
  listReasonCodes,
  listSubstances,
} from "../catalogue";
import type { ReasonKind } from "../types";
import { keys } from "./keys";

// The catalogue changes only when a rule change is approved, so it is kept for 5 minutes.
const STALE_MS = 5 * 60_000;

export function useSubstances() {
  return useQuery({ queryKey: keys.substances, queryFn: listSubstances, staleTime: STALE_MS });
}

export function useClasses() {
  return useQuery({ queryKey: keys.classes, queryFn: listClasses, staleTime: STALE_MS });
}

export function useLicenceTypes() {
  return useQuery({ queryKey: keys.licenceTypes, queryFn: listLicenceTypes, staleTime: STALE_MS });
}

export function useApprovalThresholds() {
  return useQuery({
    queryKey: keys.approvalThresholds,
    queryFn: listApprovalThresholds,
    staleTime: STALE_MS,
  });
}

export function useReasonCodes(kind: ReasonKind) {
  return useQuery({
    queryKey: keys.reasonCodes(kind),
    queryFn: () => listReasonCodes(kind),
    staleTime: STALE_MS,
  });
}
