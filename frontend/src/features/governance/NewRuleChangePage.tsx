import { Alert, Anchor, Card, Radio, Stack, Text, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { useDraftRuleChange } from "@/api/hooks/governance";
import type { ProposalKind } from "@/api/types";
import { useSession } from "@/auth/SessionProvider";
import {
  LicenceTypeForm,
  RuleVersionForm,
  ThresholdForm,
  type DraftFormProps,
  type DraftValues,
} from "./DraftForms";
import { canDraft } from "./drafting";
import { RULE_CHANGES_PATH, ruleChangePath } from "./paths";

const KINDS: ProposalKind[] = ["NEW_LICENCE_TYPE", "RULE_VERSION", "APPROVAL_THRESHOLD"];

const FORMS: Record<ProposalKind, (props: DraftFormProps) => JSX.Element> = {
  NEW_LICENCE_TYPE: LicenceTypeForm,
  RULE_VERSION: RuleVersionForm,
  APPROVAL_THRESHOLD: ThresholdForm,
};

// Drafting a rule change: pick the kind, then fill that kind's form with a justification. The
// server checks everything again; a 422 lists its reasons above the form, and a draft that is
// saved opens on its detail page.
export function NewRuleChangePage() {
  const { t } = useTranslation();
  const { user } = useSession();
  const navigate = useNavigate();
  const draft = useDraftRuleChange();
  const [kind, setKind] = useState<ProposalKind | null>(null);

  const back = (
    <Anchor component={Link} to={RULE_CHANGES_PATH} size="sm">
      {t("ruleChange.back")}
    </Anchor>
  );

  if (!canDraft(user)) {
    return (
      <Stack>
        {back}
        <Title order={1}>{t("pages.newRuleChange")}</Title>
        <Alert color="gray">{t("draft.notDrafter")}</Alert>
      </Stack>
    );
  }

  const submit = ({ payload, justification }: DraftValues) => {
    if (!kind) return;
    draft.mutate(
      { kind, payload, justification },
      {
        onSuccess: (change) => {
          notifications.show({ message: t("draft.sent") });
          navigate(ruleChangePath(change.id));
        },
      },
    );
  };

  const Form = kind ? FORMS[kind] : null;

  return (
    <Stack>
      {back}
      <Title order={1}>{t("pages.newRuleChange")}</Title>
      <Card withBorder padding="md">
        <Radio.Group
          label={t("draft.kind")}
          value={kind ?? ""}
          onChange={(value) => {
            setKind(value as ProposalKind);
            draft.reset();
          }}
        >
          <Stack gap="sm" mt="xs">
            {KINDS.map((option) => (
              <Radio
                key={option}
                value={option}
                label={t(`draft.kinds.${option}`)}
                description={t(`draft.kindHints.${option}`)}
              />
            ))}
          </Stack>
        </Radio.Group>
      </Card>
      {Form ? (
        <Card withBorder padding="md">
          <Form key={kind} onSubmit={submit} submitting={draft.isPending} error={draft.error} />
        </Card>
      ) : (
        <Text c="dimmed">{t("draft.pickKind")}</Text>
      )}
    </Stack>
  );
}
