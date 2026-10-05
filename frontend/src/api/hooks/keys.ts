import type { QueryClient, QueryFunctionContext, QueryKey } from "@tanstack/react-query";
import type { RegisterFilters, RegisterSearch } from "../licensing";
import type { TransactionFilters } from "../transactions";
import type { ProposalStatus, ReasonKind } from "../types";

// Every query key in one place. A key that takes arguments starts with its area's constant,
// so invalidating the constant refreshes every variant.
export const keys = {
  me: ["me"],
  home: ["home"],
  transactions: ["transactions"],
  transactionList: (filters: TransactionFilters) => ["transactions", "list", filters],
  transaction: (reference: string) => ["transactions", "detail", reference],
  alerts: ["alerts"],
  batches: ["batches"],
  batch: (id: number) => ["batches", id],
  reviewSettings: ["review-settings"],
  myLicences: ["licences", "mine"],
  myStock: ["stock", "mine"],
  register: ["register"],
  registerSearch: (filters: RegisterFilters, search: RegisterSearch) => [
    "register",
    "search",
    filters,
    search,
  ],
  licence: (id: number) => ["register", "licence", id],
  substances: ["catalogue", "substances"],
  classes: ["catalogue", "classes"],
  licenceTypes: ["catalogue", "licence-types"],
  approvalThresholds: ["catalogue", "approval-thresholds"],
  catalogue: ["catalogue"],
  reasonCodes: (kind: ReasonKind) => ["reason-codes", kind],
  ruleChanges: ["rule-changes"],
  ruleChangeList: (status: ProposalStatus | "") => ["rule-changes", "list", status],
  ruleChange: (id: number) => ["rule-changes", "detail", id],
  demoPersonas: ["demo", "personas"],
  demoInbox: ["demo", "inbox"],
} as const;

/** Home counts and alerts refresh this often (W7). */
export const POLL_MS = 30_000;

/** Refetch `queryKeys` and the home counts after something changed on the server. */
export function invalidate(client: QueryClient, ...queryKeys: QueryKey[]): Promise<void> {
  return Promise.all(
    [keys.home, ...queryKeys].map((queryKey) => client.invalidateQueries({ queryKey })),
  ).then(() => undefined);
}

/**
 * For the polled queries: a fetch of something already shown (the 30-second interval, a
 * refocus) is a background refresh, which does not extend the session; the first load is not.
 */
export function isBackground({ client, queryKey }: QueryFunctionContext): boolean {
  return client.getQueryData(queryKey) !== undefined;
}
