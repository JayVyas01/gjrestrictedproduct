import { Anchor, Button, Card, Group, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useHome } from "@/api/hooks/home";
import { useSession } from "@/auth/SessionProvider";
import { ActionButton, type CardAction } from "@/components/Action";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { Section } from "@/components/Section";
import { WhatsNextCard } from "@/components/WhatsNextCard";
import { RULE_CHANGES_PATH } from "@/features/governance/paths";
import { useAlertsDrawer } from "@/layout/AlertsDrawerContext";
import type { OverviewPaths } from "./paths";

interface Line {
  text: string;
  action: CardAction;
}

function WhatsNext({ paths }: { paths: OverviewPaths }) {
  const { t } = useTranslation();
  const home = useHome();
  const drawer = useAlertsDrawer();
  if (home.isPending) return <LoadingSkeleton />;
  if (home.isError) return <ErrorNotice error={home.error} />;

  const counts = home.data.counts;
  const ruleChanges = { label: t("overview.reviewRuleChanges"), to: RULE_CHANGES_PATH };
  const lines: Line[] = [];
  const add = (count: number | undefined, text: (count: number) => string, action: CardAction) => {
    if (count && count > 0) lines.push({ text: text(count), action });
  };
  // Only the Head Authority's home carries the rule-change counts.
  add(counts.rule_changes_awaiting_you, (count) => t("overview.awaitingYou", { count }), ruleChanges);
  add(
    counts.your_open_rule_changes,
    (count) => t("authority.yourOpen", { count }),
    { label: t("authority.viewRuleChanges"), to: RULE_CHANGES_PATH },
  );
  add(
    counts.unacknowledged_alerts,
    (count) => t("personnel.alerts", { count }),
    { label: t("personnel.openAlerts"), onClick: drawer.open },
  );
  add(
    counts.awaiting_superintendent,
    (count) => t("overview.awaitingSuperintendent", { count }),
    { label: t("overview.viewTransactions"), to: paths.transactions },
  );

  if (lines.length === 0) {
    return <WhatsNextCard title={t("home.whatsNext")} body={t("overview.nothing")} />;
  }
  return (
    <WhatsNextCard title={t("home.whatsNext")}>
      <Stack gap="sm" mt="sm">
        {lines.map((line) => (
          <Group key={line.text} justify="space-between" gap="sm">
            <Text>{line.text}</Text>
            <ActionButton action={line.action} />
          </Group>
        ))}
      </Stack>
    </WhatsNextCard>
  );
}

function QuickLinks({ paths, head }: { paths: OverviewPaths; head: boolean }) {
  const { t } = useTranslation();
  const drawer = useAlertsDrawer();
  const links = [
    {
      to: RULE_CHANGES_PATH,
      label: t("nav.ruleChanges"),
      hint: t(head ? "overview.ruleChangesHint" : "overview.ruleChangesHintOwner"),
    },
    { to: paths.transactions, label: t("nav.transactions"), hint: t("overview.transactionsHint") },
    { to: paths.batches, label: t("nav.batches"), hint: t("overview.batchesHint") },
    {
      to: paths.reviewPeriods,
      label: t("nav.reviewPeriods"),
      hint: t("overview.reviewPeriodsHint"),
    },
    { to: paths.licences, label: t("nav.licences"), hint: t("overview.licencesHint") },
  ];
  return (
    <Section title={t("overview.goTo")}>
      <SimpleGrid
        component="ul"
        cols={{ base: 1, sm: 2 }}
        p={0}
        m={0}
        style={{ listStyle: "none" }}
      >
        {links.map((link) => (
          <Card component="li" key={link.to} withBorder padding="md">
            <Anchor component={Link} to={link.to} fw={600}>
              {link.label}
            </Anchor>
            <Text size="sm" mt={4}>
              {link.hint}
            </Text>
          </Card>
        ))}
        <Card component="li" withBorder padding="md">
          <Button variant="subtle" px={0} onClick={drawer.open} style={{ alignSelf: "start" }}>
            {t("overview.alerts")}
          </Button>
          <Text size="sm" mt={4}>
            {t("overview.alertsHint")}
          </Text>
        </Card>
      </SimpleGrid>
    </Section>
  );
}

interface Props {
  /** The role's own read-only screens. */
  paths: OverviewPaths;
}

// The Head Authority's home and the Software Owner's overview: What's next (rule changes waiting
// for the Head's approval, unacknowledged alerts, transactions waiting for a superintendent), then
// links to the read-only lists. Nothing here changes a record; rule changes are decided on their
// own page.
export function OverviewHomePage({ paths }: Props) {
  const { t } = useTranslation();
  const { user } = useSession();
  const head = user?.role === "HEAD_AUTHORITY";
  return (
    <Stack gap="xl">
      <Title order={1}>{t(head ? "pages.headHome" : "pages.overview")}</Title>
      <WhatsNext paths={paths} />
      <QuickLinks paths={paths} head={head} />
    </Stack>
  );
}
