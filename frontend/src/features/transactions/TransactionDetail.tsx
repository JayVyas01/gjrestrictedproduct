import { Alert, Card, Group, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import { useId, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { TimelineEvent, TransactionDetail as Detail, TransactionStatus } from "@/api/types";
import { DateText } from "@/components/DateText";
import { Qty } from "@/components/Qty";
import { StatusBadge } from "@/components/StatusBadge";
import { StatusTimeline } from "@/components/StatusTimeline";
import { WhatsNextCard } from "@/components/WhatsNextCard";
import { WARNING_COLOR } from "@/theme";
import { CancelSale, canCancel } from "./CancelSale";
import { DecisionPanel, offeredOutcomes } from "./DecisionPanel";

const PENDING_STEP: Partial<Record<TransactionStatus, TimelineEvent["step"]>> = {
  AWAITING_BUYER: "BUYER",
  AWAITING_OFFICER: "OFFICER",
  AWAITING_SUPERINTENDENT: "SUPERINTENDENT",
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return (
    <Card component="section" aria-labelledby={id} withBorder padding="lg">
      <Title order={2} size="h3" id={id} mb="sm">
        {title}
      </Title>
      {children}
    </Card>
  );
}

/** Label and value pairs as a description list. */
function Facts({ items }: { items: [string, ReactNode][] }) {
  return (
    <SimpleGrid component="dl" cols={{ base: 1, xs: 2 }} spacing="sm" m={0}>
      {items.map(([label, value]) => (
        <div key={label}>
          <Text component="dt" size="sm" c="dimmed">
            {label}
          </Text>
          <Text component="dd" fw={500} m={0}>
            {value}
          </Text>
        </div>
      ))}
    </SimpleGrid>
  );
}

interface Props {
  transaction: Detail;
}

// One transaction as its viewer may see it: status and next action, summary, transport,
// designated officer, approval chain and timeline, then what the viewer can do. Shared by the
// licensee and personnel screens. The buyer's stock-limit sentence is only ever shown to the
// buyer (the server sends it to no one else).
export function TransactionDetail({ transaction: tx }: Props) {
  const { t } = useTranslation();
  const stockLimit = tx.your_role === "buyer" ? tx.stock_limit_problem : null;
  const deciding = offeredOutcomes(tx).length > 0;

  return (
    <Stack gap="lg">
      <Group gap="sm">
        <StatusBadge status={tx.status} awaitingYou={tx.can_decide} />
        {tx.can_decide && (
          <Text c="dimmed" size="sm">
            {tx.status_label}
          </Text>
        )}
      </Group>

      {tx.next_action && <WhatsNextCard title={t("transaction.next")} body={tx.next_action} />}

      {stockLimit && (
        <Alert
          color={WARNING_COLOR}
          variant="light"
          icon={<IconAlertTriangle aria-hidden />}
        >
          {stockLimit}
        </Alert>
      )}

      {deciding && (
        <Section title={t("transaction.decision")}>
          <DecisionPanel key={tx.reference} transaction={tx} />
        </Section>
      )}
      {canCancel(tx) && <CancelSale reference={tx.reference} />}

      <Section title={t("transaction.summary")}>
        <Facts
          items={[
            [t("transaction.substance"), tx.substance],
            [t("transaction.quantity"), <Qty key="qty" value={tx.quantity} unit={tx.unit} />],
            [t("transaction.seller"), tx.seller_name],
            [t("transaction.buyer"), tx.buyer_name],
            [t("transaction.started"), <DateText key="at" iso={tx.created_at} withTime />],
            [t("transaction.approval"), tx.approval_chain_label],
            [t("transaction.officer"), tx.designated_officer],
          ]}
        />
      </Section>

      <Section title={t("transaction.transport")}>
        <Facts
          items={[
            [t("transaction.transporter"), tx.transport.name],
            [t("transaction.transporterId"), tx.transport.id_number],
            [t("transaction.vehicle"), tx.transport.vehicle_number],
            [t("transaction.route"), tx.transport.route],
          ]}
        />
      </Section>

      <Section title={t("transaction.progress")}>
        <StatusTimeline events={tx.timeline} pending={PENDING_STEP[tx.status] ?? null} />
      </Section>
    </Stack>
  );
}
