import type { TFunction } from "i18next";
import type { BatchSummary } from "@/api/types";
import { formatDate } from "@/components/DateText";

/** "14 Sep 2026 to 28 Sep 2026": a batch's review period. */
export function batchPeriod(t: TFunction, batch: BatchSummary): string {
  return t("batches.period", {
    start: formatDate(batch.period_start),
    end: formatDate(batch.period_end),
  });
}

/** "4 transactions, 2 flags". */
export function batchCounts(t: TFunction, batch: BatchSummary): string {
  return t("batches.counts", {
    items: t("batches.items", { count: batch.item_count }),
    flags: t("batches.flags", { count: batch.flag_count }),
  });
}

/** "Signed by GJ… on 4 Oct 2026, 12:00 pm", or null while unsigned. */
export function signedLine(t: TFunction, batch: BatchSummary, withTime = true): string | null {
  if (!batch.signed_by || !batch.signed_at) return null;
  return t("batches.signedBy", {
    who: batch.signed_by,
    date: formatDate(batch.signed_at, withTime),
  });
}
