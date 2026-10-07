import { Badge } from "@mantine/core";
import { useTranslation } from "react-i18next";
import type { BatchStatus, ProposalStatus, TransactionStatus } from "@/api/types";
import { AWAITING_YOU_COLOR, STATUS_COLORS, type StatusTone } from "@/theme";

/** A status badge keeps its whole word: in a narrow table cell it widens the cell instead of
 * cutting the status off with an ellipsis. */
const WHOLE_WORD = { miw: "max-content" } as const;

export function statusTone(status: TransactionStatus): StatusTone {
  if (status === "APPROVED") return "approved";
  if (status === "CANCELLED") return "cancelled";
  if (status.startsWith("REJECTED")) return "rejected";
  return "waiting";
}

interface Props {
  status: TransactionStatus;
  /**
   * The words to show: the server's `status_for_you` ("Requires your approval", "Requires buyer
   * approval", or the status label). Without it, the status's own words.
   */
  label?: string;
  /** The viewer must decide (`awaiting_you`): the attention colour, and "Awaiting you" unless
   * `label` says otherwise. */
  awaitingYou?: boolean;
}

// A transaction's status as words on a coloured badge (the colour is never the only signal).
export function StatusBadge({ status, label, awaitingYou = false }: Props) {
  const { t } = useTranslation();
  if (awaitingYou) {
    return (
      <Badge
        color={AWAITING_YOU_COLOR}
        variant="filled"
        tt="none"
        {...WHOLE_WORD}
        data-tone="awaiting-you"
      >
        {label ?? t("status.awaitingYou")}
      </Badge>
    );
  }
  const tone = statusTone(status);
  return (
    <Badge color={STATUS_COLORS[tone]} variant="filled" tt="none" {...WHOLE_WORD} data-tone={tone}>
      {label ?? t(`status.${status}`)}
    </Badge>
  );
}

/** A batch: open is waiting, overdue red, signed green. */
export function batchTone(status: BatchStatus): StatusTone {
  if (status === "SIGNED") return "approved";
  if (status === "OVERDUE") return "rejected";
  return "waiting";
}

// A superintendent batch's status, worded and coloured like a transaction's (`data-tone` names the
// colour for tests).
export function BatchStatusBadge({ status }: { status: BatchStatus }) {
  const { t } = useTranslation();
  const tone = batchTone(status);
  return (
    <Badge color={STATUS_COLORS[tone]} variant="filled" tt="none" {...WHOLE_WORD} data-tone={tone}>
      {t(`batchStatus.${status}`)}
    </Badge>
  );
}

/** A rule change: open is waiting, approved green, rejected red, withdrawn grey. */
export function proposalTone(status: ProposalStatus): StatusTone {
  if (status === "APPROVED") return "approved";
  if (status === "REJECTED") return "rejected";
  if (status === "WITHDRAWN") return "cancelled";
  return "waiting";
}

// A rule change's status, worded and coloured like a transaction's.
export function ProposalStatusBadge({ status }: { status: ProposalStatus }) {
  const { t } = useTranslation();
  const tone = proposalTone(status);
  return (
    <Badge color={STATUS_COLORS[tone]} variant="filled" tt="none" {...WHOLE_WORD} data-tone={tone}>
      {t(`proposalStatus.${status}`)}
    </Badge>
  );
}
