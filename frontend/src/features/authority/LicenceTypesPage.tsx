import { Accordion, Loader, Stack, Table, Text, Title } from "@mantine/core";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { useApprovalThresholds, useLicenceTypes } from "@/api/hooks/catalogue";
import type { LicenceType, LicenceTypeRule, ScopeKind } from "@/api/types";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { Qty } from "@/components/Qty";
import { Loaded, Section } from "@/components/Section";

function scopeText(t: TFunction, scope: string, kind: ScopeKind): string {
  return t(`licenceTypes.scopeValue_${kind}`, { scope });
}

/** "Buy, sell, transport", only what the rule allows; "Nothing" when it allows none. */
function allows(t: TFunction, rule: LicenceTypeRule): string {
  const words = [
    rule.may_buy && t("licenceTypes.buy"),
    rule.may_sell && t("licenceTypes.sell"),
    rule.may_transport && t("licenceTypes.transport"),
  ].filter((word): word is string => Boolean(word));
  if (words.length === 0) return t("licenceTypes.nothing");
  const sentence = words.join(", ");
  return sentence.charAt(0).toUpperCase() + sentence.slice(1);
}

function Rules({ type }: { type: LicenceType }) {
  const { t } = useTranslation();
  if (type.rules.length === 0) return <Text c="dimmed">{t("licenceTypes.noRules")}</Text>;
  return (
    <Table.ScrollContainer minWidth={720}>
      <Table striped aria-label={t("licenceTypes.rules", { name: type.name })}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th scope="col">{t("licenceTypes.scope")}</Table.Th>
            <Table.Th scope="col">{t("licenceTypes.allows")}</Table.Th>
            <Table.Th scope="col">{t("licenceTypes.stockLimit")}</Table.Th>
            <Table.Th scope="col">{t("licenceTypes.perTransaction")}</Table.Th>
            <Table.Th scope="col">{t("licenceTypes.validity")}</Table.Th>
            <Table.Th scope="col">{t("licenceTypes.version")}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {type.rules.map((rule) => (
            <Table.Tr key={`${rule.scope_kind}-${rule.scope_code}`}>
              <Table.Td>{scopeText(t, rule.scope, rule.scope_kind)}</Table.Td>
              <Table.Td>{allows(t, rule)}</Table.Td>
              <Table.Td>
                <Qty value={rule.max_stock_qty} unit={rule.unit} />
              </Table.Td>
              <Table.Td>
                <Qty value={rule.max_per_transaction_qty} unit={rule.unit} />
              </Table.Td>
              <Table.Td>{t("licenceTypes.months", { count: rule.validity_months })}</Table.Td>
              <Table.Td>{rule.version}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

function Types() {
  const { t } = useTranslation();
  const types = useLicenceTypes();
  if (types.isPending) return <Loader role="status" aria-label={t("common.loading")} />;
  if (types.isError) return <ErrorNotice error={types.error} />;
  if (types.data.length === 0) {
    return <EmptyState title={t("licenceTypes.empty")} body={t("licenceTypes.emptyBody")} />;
  }
  return (
    <Accordion variant="separated" multiple>
      {types.data.map((type) => (
        <Accordion.Item key={type.code} value={type.code}>
          <Accordion.Control>
            <Text component="span" fw={600}>
              {type.name}
            </Text>{" "}
            <Text component="span" size="sm" c="dimmed">
              {t("licenceTypes.code", { code: type.code })}
            </Text>
          </Accordion.Control>
          <Accordion.Panel>
            <Stack gap="sm">
              {type.description && <Text>{type.description}</Text>}
              <Rules type={type} />
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>
      ))}
    </Accordion>
  );
}

function Thresholds() {
  const { t } = useTranslation();
  const thresholds = useApprovalThresholds();
  return (
    <Section title={t("licenceTypes.thresholds")}>
      <Text>{t("licenceTypes.thresholdsIntro")}</Text>
      <Loaded query={thresholds}>
        {(list) =>
          list.length === 0 ? (
            <Text c="dimmed">{t("licenceTypes.noThresholds")}</Text>
          ) : (
            <Table.ScrollContainer minWidth={480}>
              <Table striped aria-label={t("licenceTypes.thresholds")}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th scope="col">{t("licenceTypes.scope")}</Table.Th>
                    <Table.Th scope="col">{t("licenceTypes.above")}</Table.Th>
                    <Table.Th scope="col">{t("licenceTypes.version")}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {list.map((threshold) => (
                    <Table.Tr key={`${threshold.scope_kind}-${threshold.scope}`}>
                      <Table.Td>{scopeText(t, threshold.scope, threshold.scope_kind)}</Table.Td>
                      <Table.Td>
                        <Qty value={threshold.superintendent_above_qty} unit={threshold.unit} />
                      </Table.Td>
                      <Table.Td>{threshold.version}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )
        }
      </Loaded>
    </Section>
  );
}

// The catalogue as it stands: an accordion per licence type listing each rule (scope, what it
// allows, the limits, validity and version), then the approval thresholds. Read-only: changes go
// through rule changes.
export function LicenceTypesPage() {
  const { t } = useTranslation();
  return (
    <Stack gap="xl">
      <Stack gap="sm">
        <Title order={1}>{t("pages.licenceTypes")}</Title>
        <Text>{t("licenceTypes.intro")}</Text>
        <Types />
      </Stack>
      <Thresholds />
    </Stack>
  );
}
