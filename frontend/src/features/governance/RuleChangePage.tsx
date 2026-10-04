import { Alert, Anchor, Card, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { useId, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { useRuleChange } from "@/api/hooks/governance";
import type { Me, RuleChange } from "@/api/types";
import { useSession } from "@/auth/SessionProvider";
import { DateText } from "@/components/DateText";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { ProposalStatusBadge } from "@/components/StatusBadge";
import { Comparison } from "./Comparison";
import { drafterText } from "./drafting";
import { RULE_CHANGES_PATH } from "./paths";
import { DecideRuleChange, WithdrawRuleChange } from "./RuleChangeActions";

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

function Facts({ items }: { items: [string, ReactNode][] }) {
  return (
    <SimpleGrid component="dl" cols={{ base: 1, xs: 2 }} spacing="sm" m={0}>
      {items.map(([label, value]) => (
        <div key={label}>
          <Text component="dt" size="sm" c="dimmed">
            {label}
          </Text>
          <Text component="dd" fw={500} m={0} style={{ whiteSpace: "pre-wrap" }}>
            {value}
          </Text>
        </div>
      ))}
    </SimpleGrid>
  );
}

/**
 * A Head Authority officer looking at their own open draft: the server never lets them decide it
 * (maker-checker), and the page says who must.
 */
export function isOwnHeadDraft(change: RuleChange, user: Me | null | undefined): boolean {
  return (
    user?.role === "HEAD_AUTHORITY" &&
    change.status === "SUBMITTED" &&
    !change.can_decide &&
    (change.can_withdraw || change.drafted_by === user.user_id)
  );
}

function Detail({ change }: { change: RuleChange }) {
  const { t } = useTranslation();
  const { user } = useSession();
  const decision = change.decision;

  return (
    <Stack gap="lg">
      <Title order={1}>{t("ruleChange.title", { kind: change.kind_label, id: change.id })}</Title>
      <div>
        <ProposalStatusBadge status={change.status} />
      </div>

      {change.can_decide && (
        <Section title={t("ruleChange.yourDecision")}>
          <DecideRuleChange change={change} />
        </Section>
      )}
      {isOwnHeadDraft(change, user) && <Alert color="gray">{t("ruleChange.ownDraft")}</Alert>}
      {change.can_withdraw && <WithdrawRuleChange id={change.id} />}

      <Section title={t("ruleChange.compare")}>
        <Comparison change={change} />
      </Section>

      <Section title={t("ruleChange.details")}>
        <Facts
          items={[
            [t("ruleChange.justification"), change.justification],
            [t("ruleChange.draftedBy"), drafterText(t, change)],
            [t("ruleChange.draftedAt"), <DateText key="at" iso={change.drafted_at} withTime />],
            [t("ruleChange.status"), <ProposalStatusBadge key="s" status={change.status} />],
          ]}
        />
      </Section>

      {decision && (
        <Section title={t("ruleChange.decision")}>
          <Facts
            items={[
              [t("ruleChange.status"), t(`proposalStatus.${decision.outcome}`)],
              [t("ruleChange.decidedAt"), <DateText key="at" iso={decision.decided_at} withTime />],
              [t("ruleChange.note"), decision.note ?? t("ruleChange.noNote")],
            ]}
          />
        </Section>
      )}
    </Stack>
  );
}

// One rule change: its status, the decision buttons (`can_decide`), the own-draft note for the
// Head Authority, Withdraw (`can_withdraw`), the before and after, the details and any decision.
export function RuleChangePage() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const changeId = /^\d+$/.test(id) ? Number(id) : NaN;
  const valid = Number.isSafeInteger(changeId);
  const change = useRuleChange(valid ? changeId : 0, valid);

  return (
    <Stack>
      <Anchor component={Link} to={RULE_CHANGES_PATH} size="sm">
        {t("ruleChange.back")}
      </Anchor>
      {valid && change.isSuccess ? (
        <Detail change={change.data} />
      ) : (
        <>
          <Title order={1}>{t("pages.ruleChangeDetail")}</Title>
          {!valid ? (
            <ErrorNotice error={new ApiError(404, "")} />
          ) : change.isError ? (
            <ErrorNotice error={change.error} />
          ) : (
            <LoadingSkeleton />
          )}
        </>
      )}
    </Stack>
  );
}
