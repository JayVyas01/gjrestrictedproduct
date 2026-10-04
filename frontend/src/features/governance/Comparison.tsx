import { Badge, SimpleGrid, Stack, Table, Text } from "@mantine/core";
import type { TFunction } from "i18next";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { ProposalKind, ProposalValues, RuleChange } from "@/api/types";
import { Qty } from "@/components/Qty";
import { scopeText } from "./drafting";

type FieldKind = "text" | "flag" | "quantity" | "months";
type FieldKey =
  | "code"
  | "name"
  | "description"
  | "may_buy"
  | "may_sell"
  | "may_transport"
  | "max_stock_qty"
  | "max_per_transaction_qty"
  | "validity_months"
  | "superintendent_above_qty";

/** The compared values of each kind, in order, and how each is shown. */
export const FIELDS: Record<ProposalKind, [FieldKey, FieldKind][]> = {
  NEW_LICENCE_TYPE: [
    ["code", "text"],
    ["name", "text"],
    ["description", "text"],
  ],
  RULE_VERSION: [
    ["may_buy", "flag"],
    ["may_sell", "flag"],
    ["may_transport", "flag"],
    ["max_stock_qty", "quantity"],
    ["max_per_transaction_qty", "quantity"],
    ["validity_months", "months"],
  ],
  APPROVAL_THRESHOLD: [["superintendent_above_qty", "quantity"]],
};

type Value = ProposalValues[string] | undefined;

/** Whether a proposed value differs from the current one (quantities compared as numbers). */
export function differs(kind: FieldKind, now: Value, proposed: Value): boolean {
  if (kind === "quantity" || kind === "months") return Number(now) !== Number(proposed);
  return now !== proposed;
}

function show(t: TFunction, kind: FieldKind, value: Value, unit: string | null): ReactNode {
  if (value === null || value === undefined || value === "") return t("ruleChange.none");
  switch (kind) {
    case "flag":
      return value ? t("common.yes") : t("common.no");
    case "quantity":
      return <Qty value={String(value)} unit={unit} />;
    case "months":
      return t("licenceTypes.months", { count: Number(value) });
    default:
      return String(value);
  }
}

function AppliesTo({ change }: { change: RuleChange }) {
  const { t } = useTranslation();
  const values = change.proposed;
  if (change.kind === "NEW_LICENCE_TYPE") return null;
  const items: [string, string][] = [];
  if (change.kind === "RULE_VERSION") {
    const name = String(values.licence_type_name ?? values.licence_type_code ?? "");
    items.push([t("ruleChange.licenceType"), name]);
  }
  items.push([t("ruleChange.scope"), scopeText(t, values)]);
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

// The before and after of a rule change: the catalogue's current values beside the proposed ones,
// each changed value highlighted and marked "Changed" in words (never by colour alone). With no
// current values: a new type or scope ("New, nothing to compare"), or a decided change.
export function Comparison({ change }: { change: RuleChange }) {
  const { t } = useTranslation();
  const { current, proposed } = change;
  const unit = typeof proposed.unit === "string" ? proposed.unit : null;
  const fields = FIELDS[change.kind];
  const nowLabel =
    current && typeof current.version === "number"
      ? t("ruleChange.nowVersion", { version: current.version })
      : t("ruleChange.now");

  return (
    <Stack gap="sm">
      <AppliesTo change={change} />
      {!current && (
        <Text fw={500}>
          {change.status === "SUBMITTED"
            ? t("ruleChange.newNothing")
            : t("ruleChange.decidedNoCompare")}
        </Text>
      )}
      {/* Narrow enough that "Proposed" stays in view on a 360 px phone (no sideways scroll). */}
      <Table.ScrollContainer minWidth={280}>
        <Table aria-label={t("ruleChange.compareTable")} verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th scope="col">{t("ruleChange.field")}</Table.Th>
              {current && <Table.Th scope="col">{nowLabel}</Table.Th>}
              <Table.Th scope="col">{t("ruleChange.proposed")}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {fields.map(([key, kind]) => {
              const changed = current !== null && differs(kind, current[key], proposed[key]);
              return (
                <Table.Tr key={key} data-changed={changed ? "true" : undefined}>
                  <Table.Th scope="row" fw={500}>
                    {t(`ruleChange.fields.${key}`)}
                  </Table.Th>
                  {current && <Table.Td>{show(t, kind, current[key], unit)}</Table.Td>}
                  <Table.Td
                    bg={changed ? "saffron.0" : undefined}
                    fw={changed ? 700 : undefined}
                  >
                    {show(t, kind, proposed[key], unit)}
                    {changed && (
                      <Badge ml="xs" color="navy" variant="outline" tt="none" miw="max-content">
                        {t("ruleChange.changed")}
                      </Badge>
                    )}
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Stack>
  );
}
