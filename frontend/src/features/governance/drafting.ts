import type { TFunction } from "i18next";
import type { Me, ProposalValues, RuleChange } from "@/api/types";
import { holdsDistrictPosition } from "@/auth/session";

/**
 * Who may draft a rule change (governance.service.may_draft): the Licensing Authority, the Head
 * Authority, or personnel holding a district position. The server checks again.
 */
export function canDraft(user: Me | null | undefined): boolean {
  if (!user) return false;
  if (user.role === "LICENSING_AUTHORITY" || user.role === "HEAD_AUTHORITY") return true;
  return user.role === "PERSONNEL" && holdsDistrictPosition(user);
}

const text = (value: ProposalValues[string] | undefined): string =>
  value === null || value === undefined ? "" : String(value);

/** "Spirits (class)" or "Whisky (substance)", from a proposal's resolved scope. */
export function scopeText(t: TFunction, values: ProposalValues): string {
  const kind = values.scope_kind === "substance" ? "substance" : "class";
  const scope = text(values.scope) || text(values.substance_code) || text(values.class_code);
  return t(`licenceTypes.scopeValue_${kind}`, { scope });
}

/** What a change is about, in one line: the new type, the type and scope, or the scope. */
export function scopeSummary(t: TFunction, change: Pick<RuleChange, "kind" | "proposed">): string {
  const values = change.proposed;
  switch (change.kind) {
    case "NEW_LICENCE_TYPE":
      return t("ruleChanges.newType", { name: text(values.name), code: text(values.code) });
    case "RULE_VERSION":
      return t("ruleChanges.typeScope", {
        type: text(values.licence_type_name) || text(values.licence_type_code),
        scope: scopeText(t, values),
      });
    case "APPROVAL_THRESHOLD":
      return scopeText(t, values);
  }
}

/** The drafter's role, with their user ID when the server sent it (Head and Software Owner). */
export function drafterText(t: TFunction, change: RuleChange): string {
  if (!change.drafted_by) return change.drafted_by_role;
  return t("ruleChanges.drafter", { role: change.drafted_by_role, id: change.drafted_by });
}
