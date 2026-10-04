import { Anchor, Card, Group, Loader, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useHome } from "@/api/hooks/home";
import { ActionButton, type CardAction } from "@/components/Action";
import { ErrorNotice } from "@/components/ErrorNotice";
import { Section } from "@/components/Section";
import { WhatsNextCard } from "@/components/WhatsNextCard";
import {
  LICENCE_TYPES_PATH,
  LICENCES_PATH,
  REVIEW_PERIODS_PATH,
  RULE_CHANGES_PATH,
} from "./paths";

interface Line {
  text: string;
  action: CardAction;
}

function WhatsNext() {
  const { t } = useTranslation();
  const home = useHome();
  if (home.isPending) return <Loader size="sm" role="status" aria-label={t("common.loading")} />;
  if (home.isError) return <ErrorNotice error={home.error} />;

  const counts = home.data.counts;
  const ruleChanges = { label: t("authority.viewRuleChanges"), to: RULE_CHANGES_PATH };
  const lines: Line[] = [];
  const add = (count: number | undefined, text: (count: number) => string, action: CardAction) => {
    if (count && count > 0) lines.push({ text: text(count), action });
  };
  add(
    counts.expiring_licences_30d,
    (count) => t("authority.expiring", { count }),
    { label: t("authority.openRegister"), to: LICENCES_PATH },
  );
  add(
    counts.districts_without_review_period,
    (count) => t("authority.noPeriod", { count }),
    { label: t("authority.setPeriods"), to: REVIEW_PERIODS_PATH },
  );
  add(counts.your_open_rule_changes, (count) => t("authority.yourOpen", { count }), ruleChanges);
  add(counts.rule_changes_submitted, (count) => t("authority.submitted", { count }), ruleChanges);

  if (lines.length === 0) {
    return <WhatsNextCard title={t("home.whatsNext")} body={t("authority.nothing")} />;
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

function QuickLinks() {
  const { t } = useTranslation();
  const links = [
    { to: LICENCES_PATH, label: t("nav.licences"), hint: t("authority.licencesHint") },
    { to: LICENCE_TYPES_PATH, label: t("nav.licenceTypes"), hint: t("authority.licenceTypesHint") },
    {
      to: REVIEW_PERIODS_PATH,
      label: t("nav.reviewPeriods"),
      hint: t("authority.reviewPeriodsHint"),
    },
    { to: RULE_CHANGES_PATH, label: t("nav.ruleChanges"), hint: t("authority.ruleChangesHint") },
  ];
  return (
    <Section title={t("authority.goTo")}>
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
      </SimpleGrid>
    </Section>
  );
}

// The Licensing Authority's home: what waits (expiring licences, districts without a review
// period, open rule changes), then a link to each of their screens.
export function AuthorityHomePage() {
  const { t } = useTranslation();
  return (
    <Stack gap="xl">
      <Title order={1}>{t("pages.authorityHome")}</Title>
      <WhatsNext />
      <QuickLinks />
    </Stack>
  );
}
