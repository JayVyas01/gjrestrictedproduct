import { Anchor, Button, Group, Loader, Stack, Table, Tabs, Text, Title } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { useRuleChanges } from "@/api/hooks/governance";
import type { ProposalStatus } from "@/api/types";
import { useSession } from "@/auth/SessionProvider";
import { DateText } from "@/components/DateText";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { ProposalStatusBadge } from "@/components/StatusBadge";
import { canDraft, drafterText, scopeSummary } from "./drafting";
import { NEW_RULE_CHANGE_PATH, ruleChangePath } from "./paths";

const TABS: ProposalStatus[] = ["SUBMITTED", "APPROVED", "REJECTED", "WITHDRAWN"];

function statusFrom(value: string | null): ProposalStatus {
  return TABS.find((tab) => tab === value) ?? "SUBMITTED";
}

function Results({ status }: { status: ProposalStatus }) {
  const { t } = useTranslation();
  const list = useRuleChanges(status);
  if (list.isPending) return <Loader role="status" aria-label={t("common.loading")} />;
  if (list.isError) return <ErrorNotice error={list.error} />;
  if (list.data.length === 0) {
    return <EmptyState title={t("ruleChanges.empty")} body={t(`ruleChanges.emptyBody.${status}`)} />;
  }
  return (
    <Table.ScrollContainer minWidth={720}>
      <Table striped aria-label={t("ruleChanges.table")} verticalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th scope="col">{t("ruleChanges.change")}</Table.Th>
            <Table.Th scope="col">{t("ruleChanges.scope")}</Table.Th>
            <Table.Th scope="col">{t("ruleChanges.draftedBy")}</Table.Th>
            <Table.Th scope="col">{t("ruleChanges.draftedOn")}</Table.Th>
            <Table.Th scope="col">{t("ruleChanges.status")}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {list.data.map((change) => (
            <Table.Tr key={change.id}>
              <Table.Td>
                <Anchor component={Link} to={ruleChangePath(change.id)} fw={600}>
                  {change.kind_label}
                </Anchor>
              </Table.Td>
              <Table.Td>{scopeSummary(t, change)}</Table.Td>
              <Table.Td>{drafterText(t, change)}</Table.Td>
              <Table.Td>
                <DateText iso={change.drafted_at} />
              </Table.Td>
              <Table.Td>
                <ProposalStatusBadge status={change.status} />
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

// Rule changes by status (Open, Approved, Rejected, Withdrawn; `?status=` in the address), each
// row with its kind (linked), what it applies to, the drafter, the date and a status badge.
// Drafters get "New rule change"; the Software Owner reads only.
export function RuleChangesPage() {
  const { t } = useTranslation();
  const { user } = useSession();
  const [search, setSearch] = useSearchParams();
  const active = statusFrom(search.get("status"));

  return (
    <Stack>
      <Group justify="space-between" wrap="wrap">
        <Title order={1}>{t("pages.ruleChanges")}</Title>
        {canDraft(user) && (
          <Button component={Link} to={NEW_RULE_CHANGE_PATH}>
            {t("ruleChanges.new")}
          </Button>
        )}
      </Group>
      {user?.role === "SOFTWARE_OWNER" && <Text c="dimmed">{t("ruleChanges.readOnly")}</Text>}
      <Tabs
        value={active}
        onChange={(value) => setSearch(value && value !== "SUBMITTED" ? { status: value } : {})}
      >
        <Tabs.List aria-label={t("ruleChanges.filter")}>
          {TABS.map((tab) => (
            <Tabs.Tab key={tab} value={tab}>
              {t(`ruleChanges.tab.${tab}`)}
            </Tabs.Tab>
          ))}
        </Tabs.List>
        {TABS.map((tab) => (
          <Tabs.Panel key={tab} value={tab} pt="md">
            {tab === active && <Results status={tab} />}
          </Tabs.Panel>
        ))}
      </Tabs>
    </Stack>
  );
}
