// The new-sale wizard's draft. It lives only in this tab's sessionStorage (never localStorage),
// under the `gj.draft.` prefix that sign-out and session end clear (auth/session.ts clearDrafts).
// It is stored with the user ID of the person who wrote it, and only that person gets it back:
// anyone else signing in on this tab finds it discarded.

import type { ApprovalChain } from "@/api/types";

export const DRAFT_KEY = "gj.draft.sale";

/** A passed check, for exactly this buyer, substance and quantity. */
export interface PassedCheck {
  key: string;
  approval_chain: ApprovalChain | null;
}

export interface SaleDraft {
  /** 0 Buyer, 1 Goods, 2 Transport, 3 Review. */
  step: number;
  gstin: string;
  /** The registered name the lookup found, once the seller said it is the right business. */
  buyerName: string;
  substanceCode: string;
  quantity: string;
  check: PassedCheck | null;
  transporterName: string;
  transporterId: string;
  vehicleNumber: string;
  route: string;
}

export function emptyDraft(): SaleDraft {
  return {
    step: 0,
    gstin: "",
    buyerName: "",
    substanceCode: "",
    quantity: "",
    check: null,
    transporterName: "",
    transporterId: "",
    vehicleNumber: "",
    route: "",
  };
}

const TEXT_FIELDS = [
  "gstin",
  "buyerName",
  "substanceCode",
  "quantity",
  "transporterName",
  "transporterId",
  "vehicleNumber",
  "route",
] as const;

function isDraft(value: unknown): value is SaleDraft {
  if (!value || typeof value !== "object") return false;
  const draft = value as Record<string, unknown>;
  const step = draft.step;
  if (typeof step !== "number" || !Number.isInteger(step) || step < 0 || step > 3) return false;
  if (!TEXT_FIELDS.every((field) => typeof draft[field] === "string")) return false;
  const check = draft.check as Record<string, unknown> | null;
  return check === null || (typeof check === "object" && typeof check.key === "string");
}

/**
 * `owner`'s saved draft, or null when there is none or it can't be read. A draft written by
 * someone else (or by nobody named) is removed, never restored.
 */
export function loadDraft(owner: string): SaleDraft | null {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    const { owner: savedBy, ...draft } = parsed as Record<string, unknown>;
    if (savedBy !== owner) {
      clearDraft();
      return null;
    }
    return isDraft(draft) ? draft : null;
  } catch {
    return null;
  }
}

export function saveDraft(draft: SaleDraft, owner: string): void {
  try {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ ...draft, owner }));
  } catch {
    // Storage full or blocked: the wizard still works, only without a draft.
  }
}

export function clearDraft(): void {
  try {
    sessionStorage.removeItem(DRAFT_KEY);
  } catch {
    // Nothing to clear.
  }
}
