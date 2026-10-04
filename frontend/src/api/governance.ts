import { apiGet, apiPost, query } from "./client";
import type { Challenge, ProposalKind, ProposalStatus, ProposalValues, RuleChange } from "./types";

export interface RuleChangeDraft {
  kind: ProposalKind;
  payload: ProposalValues;
  justification: string;
}

export interface RuleChangeDecision {
  challenge_id: string;
  code: string;
  outcome: "APPROVE" | "REJECT";
  /** Required (10 characters or more) when rejecting. */
  note?: string;
}

const base = (id: number) => `/api/rule-changes/${id}`;

export function listRuleChanges(status: ProposalStatus | "" = ""): Promise<RuleChange[]> {
  return apiGet<RuleChange[]>(`/api/rule-changes${query({ status })}`);
}

export function getRuleChange(id: number): Promise<RuleChange> {
  return apiGet<RuleChange>(base(id));
}

export function draftRuleChange(draft: RuleChangeDraft): Promise<RuleChange> {
  return apiPost<RuleChange>("/api/rule-changes", draft);
}

export function withdrawRuleChange(id: number): Promise<RuleChange> {
  return apiPost<RuleChange>(`${base(id)}/withdraw`);
}

export function requestRuleChangeCode(id: number): Promise<Challenge> {
  return apiPost<Challenge>(`${base(id)}/decision-code`);
}

export function decideRuleChange(id: number, decision: RuleChangeDecision): Promise<RuleChange> {
  return apiPost<RuleChange>(`${base(id)}/decide`, decision);
}
