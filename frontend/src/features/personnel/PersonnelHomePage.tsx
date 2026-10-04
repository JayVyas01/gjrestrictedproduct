import { Anchor, Card, Group, Stack, Text, Title } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useAlerts } from "@/api/hooks/alerts";
import { useHome } from "@/api/hooks/home";
import { useTransactions } from "@/api/hooks/transactions";
import { holdsDistrictPosition } from "@/auth/session";
import { useSession } from "@/auth/SessionProvider";
import { ActionButton, type CardAction } from "@/components/Action";
import { DateText, formatDate } from "@/components/DateText";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { Qty } from "@/components/Qty";
import { Loaded, Section } from "@/components/Section";
import { WhatsNextCard } from "@/components/WhatsNextCard";
import { TransactionList } from "@/features/transactions/TransactionList";
import { useAlertsDrawer } from "@/layout/AlertsDrawerContext";
import { NOT_ALLOWED_COLOR } from "@/theme";
import { BATCHES_PATH, DECISION_QUEUE_PATH, PERSONNEL_TRANSACTIONS_PATH } from "./paths";

const LATEST_ALERTS = 3;
const QUEUE = { awaiting: "me" } as const;

interface Line {
  text: string;
  action: CardAction;
  /** Overdue batches are shown in red. */
  overdue?: boolean;
}

function WhatsNext() {
  const { t } = useTranslation();
  const { user } = useSession();
  const home = useHome();
  const drawer = useAlertsDrawer();
  if (home.isPending) return <LoadingSkeleton />;
  if (home.isError) return <ErrorNotice error={home.error} />;

  const counts = home.data.counts;
  const lines: Line[] = [];
  const waiting = counts.awaiting_your_decision ?? 0;
  if (waiting > 0) {
    lines.push({
      text: t("personnel.awaiting", { count: waiting }),
      action: { label: t("personnel.reviewQueue"), to: DECISION_QUEUE_PATH },
    });
  }
  const alerts = counts.unacknowledged_alerts ?? 0;
  if (alerts > 0) {
    lines.push({
      text: t("personnel.alerts", { count: alerts }),
      action: { label: t("personnel.openAlerts"), onClick: drawer.open },
    });
  }
  if (user && holdsDistrictPosition(user)) {
    const batches = { label: t("personnel.reviewBatches"), to: BATCHES_PATH };
    const overdue = counts.overdue_batches ?? 0;
    if (overdue > 0) {
      lines.push({ text: t("personnel.overdue", { count: overdue }), action: batches, overdue: true });
    } else if (counts.next_due) {
      lines.push({
        text: t("personnel.batchDue", { date: formatDate(counts.next_due) }),
        action: batches,
      });
    }
  }

  if (lines.length === 0) {
    return <WhatsNextCard title={t("home.whatsNext")} body={t("personnel.nothing")} />;
  }
  return (
    <WhatsNextCard title={t("home.whatsNext")}>
      <Stack gap="sm" mt="sm">
        {lines.map((line) => (
          <Group key={line.text} justify="space-between" gap="sm">
            <Text
              fw={line.overdue ? 700 : undefined}
              c={line.overdue ? NOT_ALLOWED_COLOR : undefined}
              data-tone={line.overdue ? "overdue" : undefined}
            >
              {line.text}
            </Text>
            <ActionButton action={line.action} />
          </Group>
        ))}
      </Stack>
    </WhatsNextCard>
  );
}

function LatestAlerts() {
  const { t } = useTranslation();
  const alerts = useAlerts();
  const drawer = useAlertsDrawer();
  return (
    <Section title={t("personnel.latestAlerts")}>
      <Loaded query={alerts}>
        {(list) => {
          const latest = list.alerts.filter((alert) => !alert.acknowledged).slice(0, LATEST_ALERTS);
          if (latest.length === 0) return <Text c="dimmed">{t("personnel.noAlerts")}</Text>;
          return (
            <>
              <Stack component="ul" gap="sm" p={0} m={0} style={{ listStyle: "none" }}>
                {latest.map((alert) => (
                  <Card component="li" key={alert.id} withBorder padding="md">
                    <Text fw={600}>{alert.kind_label}</Text>
                    <Text size="sm">
                      {alert.transaction_reference}: {alert.substance},{" "}
                      <Qty value={alert.quantity} unit={alert.unit} />
                    </Text>
                    <Text size="sm">
                      {t("transactions.between", {
                        seller: alert.seller_name,
                        buyer: alert.buyer_name,
                      })}
                    </Text>
                    <Text size="sm" c="dimmed">
                      <DateText iso={alert.created_at} withTime />
                    </Text>
                  </Card>
                ))}
              </Stack>
              <Group>
                <ActionButton action={{ label: t("personnel.openAlerts"), onClick: drawer.open }} />
              </Group>
            </>
          );
        }}
      </Loaded>
    </Section>
  );
}

// Personnel's home: what waits for them (decisions, alerts and, for a district position, the
// next batch or overdue batches in red), the decision queue and the latest unacknowledged alerts.
export function PersonnelHomePage() {
  const { t } = useTranslation();
  const queue = useTransactions(QUEUE);

  return (
    <Stack gap="xl">
      <Title order={1}>{t("pages.personnelHome")}</Title>

      <WhatsNext />

      <Section title={t("personnel.queue")}>
        <Loaded query={queue}>
          {(list) =>
            list.length === 0 ? (
              <Text c="dimmed">{t("personnel.queueEmpty")}</Text>
            ) : (
              <TransactionList
                transactions={list}
                label={t("personnel.queue")}
                basePath={PERSONNEL_TRANSACTIONS_PATH}
                awaitingYou
                showChain
              />
            )
          }
        </Loaded>
        <Anchor component={Link} to={PERSONNEL_TRANSACTIONS_PATH}>
          {t("personnel.allTransactions")}
        </Anchor>
      </Section>

      <LatestAlerts />
    </Stack>
  );
}
