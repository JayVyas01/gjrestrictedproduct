// The wizard's input rules, matching the backend (transactions/serializers.py and the GSTIN
// pattern in licensing/service.py), so the seller learns what to fix before anything is sent.

import type { SaleDraft } from "./draft";

/** Same as the backend's GSTIN_PATTERN (after it uppercases and trims). */
export const GSTIN_PATTERN = /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;
/** Same as NewTransactionSerializer.vehicle_number. */
export const VEHICLE_PATTERN = /^[A-Za-z]{2}\s?\d{1,2}\s?[A-Za-z]{0,3}\s?\d{4}$/;
/** DecimalField(max_digits=12, decimal_places=3): up to 9 whole digits and 3 decimals. */
export const QUANTITY_PATTERN = /^\d{1,9}(\.\d{1,3})?$/;

export const MAX_LENGTH = {
  gstin: 15,
  transporterName: 120,
  transporterId: 40,
  vehicleNumber: 16,
  route: 300,
} as const;

export type Field =
  | "gstin"
  | "substanceCode"
  | "quantity"
  | "check"
  | "transporterName"
  | "transporterId"
  | "vehicleNumber"
  | "route";

/** The i18n keys of the wizard's own field messages. */
export type Message =
  | "sale.gstinInvalid"
  | "sale.buyerNeeded"
  | "sale.substanceRequired"
  | "sale.quantityInvalid"
  | "sale.checkNeeded"
  | "sale.required"
  | "sale.vehicleInvalid";

/** Field → the message to show under it. */
export type FieldErrors = Partial<Record<Field, Message>>;

/** The GSTIN as typed, tidied: capitals, no spaces. */
export function normaliseGstin(value: string): string {
  return value.toUpperCase().replace(/\s+/g, "").slice(0, MAX_LENGTH.gstin);
}

export function gstinError(gstin: string): Message | undefined {
  return GSTIN_PATTERN.test(gstin) ? undefined : "sale.gstinInvalid";
}

export function quantityValid(quantity: string): boolean {
  const value = quantity.trim();
  return QUANTITY_PATTERN.test(value) && Number(value) > 0;
}

/** What a passed check is valid for: this buyer, this substance, this quantity. */
export function checkKey(sale: { buyer_gstin: string; substance_code: string; quantity: string }) {
  return `${sale.buyer_gstin}|${sale.substance_code}|${sale.quantity.trim()}`;
}

export function draftCheckKey(draft: SaleDraft): string {
  return checkKey({
    buyer_gstin: draft.gstin,
    substance_code: draft.substanceCode,
    quantity: draft.quantity,
  });
}

/** Has the current buyer, substance and quantity passed a check? */
export function checkPassed(draft: SaleDraft): boolean {
  return draft.check !== null && draft.check.key === draftCheckKey(draft);
}

export function buyerErrors(draft: SaleDraft): FieldErrors {
  const format = gstinError(draft.gstin);
  if (format) return { gstin: format };
  return draft.buyerName ? {} : { gstin: "sale.buyerNeeded" };
}

/** The substance and quantity only (what "Check" needs). */
export function goodsFieldErrors(draft: SaleDraft): FieldErrors {
  const errors: FieldErrors = {};
  if (!draft.substanceCode) errors.substanceCode = "sale.substanceRequired";
  if (!quantityValid(draft.quantity)) errors.quantity = "sale.quantityInvalid";
  return errors;
}

export function goodsErrors(draft: SaleDraft): FieldErrors {
  const errors = goodsFieldErrors(draft);
  if (Object.keys(errors).length === 0 && !checkPassed(draft)) errors.check = "sale.checkNeeded";
  return errors;
}

export function transportErrors(draft: SaleDraft): FieldErrors {
  const errors: FieldErrors = {};
  if (!draft.transporterName.trim()) errors.transporterName = "sale.required";
  if (!draft.transporterId.trim()) errors.transporterId = "sale.required";
  if (!draft.vehicleNumber.trim()) errors.vehicleNumber = "sale.required";
  else if (!VEHICLE_PATTERN.test(draft.vehicleNumber.trim()))
    errors.vehicleNumber = "sale.vehicleInvalid";
  if (!draft.route.trim()) errors.route = "sale.required";
  return errors;
}

/** The errors that stop the seller leaving `step` forwards. */
export function stepErrors(step: number, draft: SaleDraft): FieldErrors {
  if (step === 0) return buyerErrors(draft);
  if (step === 1) return goodsErrors(draft);
  if (step === 2) return transportErrors(draft);
  return {};
}

/** The furthest step a (restored) draft may be on: earlier steps must still hold. */
export function reachableStep(draft: SaleDraft): number {
  for (let step = 0; step < draft.step; step += 1) {
    if (Object.keys(stepErrors(step, draft)).length > 0) return step;
  }
  return draft.step;
}
