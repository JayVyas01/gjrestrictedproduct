import { Badge } from "@mantine/core";
import { useTranslation } from "react-i18next";
import type { TransactionStatus } from "@/api/types";
import { AWAITING_YOU_COLOR, STATUS_COLORS, type StatusTone } from "@/theme";

export function statusTone(status: TransactionStatus): StatusTone {
  if (status === "APPROVED") return "approved";
  if (status === "CANCELLED") return "cancelled";
  if (status.startsWith("REJECTED")) return "rejected";
  return "waiting";
}

interface Props {
  status: TransactionStatus;
  /** The viewer can decide (`can_decide`): "Awaiting you" replaces the status. */
  awaitingYou?: boolean;
}

// A transaction's status as a word on a coloured badge (the colour is never the only signal).
export function StatusBadge({ status, awaitingYou = false }: Props) {
  const { t } = useTranslation();
  if (awaitingYou) {
    return (
      <Badge color={AWAITING_YOU_COLOR} variant="filled" tt="none">
        {t("status.awaitingYou")}
      </Badge>
    );
  }
  return (
    <Badge color={STATUS_COLORS[statusTone(status)]} variant="filled" tt="none">
      {t(`status.${status}`)}
    </Badge>
  );
}
