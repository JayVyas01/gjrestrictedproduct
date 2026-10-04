import { Anchor, Card, Group, Stack, Table, Text } from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import type { TransactionSummary } from "@/api/types";
import { DateText } from "@/components/DateText";
import { Qty } from "@/components/Qty";
import { StatusBadge } from "@/components/StatusBadge";

/** Under 768 px (Mantine's `sm`) the rows become stacked cards. */
const STACKED = "(max-width: 47.99em)";

/** The other party for a licensee; both parties for anyone else (officers, authorities). */
export function otherParty(t: TFunction, tx: TransactionSummary): string {
  if (tx.your_role === "seller") return tx.buyer_name;
  if (tx.your_role === "buyer") return tx.seller_name;
  return t("transactions.between", { seller: tx.seller_name, buyer: tx.buyer_name });
}

interface Props {
  transactions: TransactionSummary[];
  /** The accessible name of the table or list. */
  label: string;
  /** Detail links go to `${basePath}/${reference}`. */
  basePath: string;
  /** Every row waits for the viewer (the "Waiting for you" filter). */
  awaitingYou?: boolean;
}

// Transactions as a table (reference, substance, quantity, other party, status, date), or as
// stacked cards on a narrow screen. Only one of the two is rendered.
export function TransactionList({ transactions, label, basePath, awaitingYou = false }: Props) {
  const { t } = useTranslation();
  const stacked = useMediaQuery(STACKED);
  const href = (tx: TransactionSummary) => `${basePath}/${encodeURIComponent(tx.reference)}`;
  const reference = (tx: TransactionSummary) => (
    <Anchor component={Link} to={href(tx)} fw={600}>
      {tx.reference}
    </Anchor>
  );

  if (stacked) {
    return (
      <Stack component="ul" gap="sm" p={0} m={0} aria-label={label} style={{ listStyle: "none" }}>
        {transactions.map((tx) => (
          <Card component="li" key={tx.reference} withBorder padding="md">
            <Group justify="space-between" wrap="wrap" gap="xs">
              {reference(tx)}
              <StatusBadge status={tx.status} awaitingYou={awaitingYou} />
            </Group>
            <Text mt="xs">
              {tx.substance}, <Qty value={tx.quantity} unit={tx.unit} />
            </Text>
            <Text size="sm">{otherParty(t, tx)}</Text>
            <Text size="sm" c="dimmed">
              <DateText iso={tx.created_at} />
            </Text>
          </Card>
        ))}
      </Stack>
    );
  }

  return (
    <Table.ScrollContainer minWidth={640}>
      <Table aria-label={label} striped highlightOnHover verticalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th scope="col">{t("transactions.reference")}</Table.Th>
            <Table.Th scope="col">{t("transactions.substance")}</Table.Th>
            <Table.Th scope="col">{t("transactions.quantity")}</Table.Th>
            <Table.Th scope="col">{t("transactions.otherParty")}</Table.Th>
            <Table.Th scope="col">{t("transactions.status")}</Table.Th>
            <Table.Th scope="col">{t("transactions.date")}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {transactions.map((tx) => (
            <Table.Tr key={tx.reference}>
              <Table.Td>{reference(tx)}</Table.Td>
              <Table.Td>{tx.substance}</Table.Td>
              <Table.Td>
                <Qty value={tx.quantity} unit={tx.unit} />
              </Table.Td>
              <Table.Td>{otherParty(t, tx)}</Table.Td>
              <Table.Td>
                <StatusBadge status={tx.status} awaitingYou={awaitingYou} />
              </Table.Td>
              <Table.Td>
                <DateText iso={tx.created_at} />
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
