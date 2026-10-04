import { Badge, Button, Card, Group, Stack, Table, Text } from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import { useTranslation } from "react-i18next";
import type { BatchItem } from "@/api/types";
import { DateText } from "@/components/DateText";
import { Qty } from "@/components/Qty";
import { STACKED } from "@/features/transactions/TransactionList";

interface Props {
  items: BatchItem[];
  /** Flagging is open (the viewer can review this unsigned batch, and it isn't read-only). */
  canFlag: boolean;
  onFlag: (item: BatchItem) => void;
}

/** An item can be flagged once, and never the superintendent's own final approval. */
export function flaggable(item: BatchItem): boolean {
  return !item.approved_by_superintendent && item.flag === null;
}

function ApprovedBy({ item }: { item: BatchItem }) {
  const { t } = useTranslation();
  return (
    <Group gap="xs" wrap="wrap">
      <span>{item.approved_by_position}</span>
      {item.approved_by_superintendent && (
        <Badge color="navy" variant="light" tt="none">
          {t("batches.approvedByYou")}
        </Badge>
      )}
    </Group>
  );
}

function FlagText({ item }: { item: BatchItem }) {
  const { t } = useTranslation();
  if (!item.flag) {
    return (
      <Text size="sm" c="dimmed">
        {t("batches.noFlag")}
      </Text>
    );
  }
  return (
    <Stack gap={2}>
      <Text size="sm" fw={600}>
        {item.flag.reason}
      </Text>
      {item.flag.comment && (
        <Text size="sm">{t("alerts.comment", { comment: item.flag.comment })}</Text>
      )}
    </Stack>
  );
}

function FlagButton({ item, onFlag }: { item: BatchItem; onFlag: Props["onFlag"] }) {
  const { t } = useTranslation();
  return (
    <Button
      size="xs"
      variant="outline"
      color="red.9"
      aria-label={t("batches.flagLabel", { reference: item.reference })}
      onClick={() => onFlag(item)}
    >
      {t("batches.flagAction")}
    </Button>
  );
}

// A batch's transactions: substance, quantity, parties, when and by which position each was
// approved ("Approved by you" on the superintendent's own final approvals), any flag, and the
// Flag action where allowed. Stacked cards under 768 px; only one of the two is rendered.
export function BatchItems({ items, canFlag, onFlag }: Props) {
  const { t } = useTranslation();
  const stacked = useMediaQuery(STACKED);
  const parties = (item: BatchItem) =>
    t("transactions.between", { seller: item.seller_name, buyer: item.buyer_name });
  const label = t("batches.itemsTitle");

  if (stacked) {
    return (
      <Stack component="ul" gap="sm" p={0} m={0} aria-label={label} style={{ listStyle: "none" }}>
        {items.map((item) => (
          <Card component="li" key={item.reference} withBorder padding="md">
            <Group justify="space-between" wrap="wrap" gap="xs">
              <Text fw={600}>{item.reference}</Text>
              {canFlag && flaggable(item) && <FlagButton item={item} onFlag={onFlag} />}
            </Group>
            <Text mt="xs">
              {item.substance}, <Qty value={item.quantity} unit={item.unit} />
            </Text>
            <Text size="sm">{parties(item)}</Text>
            <Text size="sm" component="div">
              <ApprovedBy item={item} />
            </Text>
            <Text size="sm" c="dimmed">
              <DateText iso={item.approved_at} withTime />
            </Text>
            <Stack mt="xs" gap={2}>
              <FlagText item={item} />
            </Stack>
          </Card>
        ))}
      </Stack>
    );
  }

  return (
    <Table.ScrollContainer minWidth={760}>
      <Table aria-label={label} striped verticalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th scope="col">{t("batches.reference")}</Table.Th>
            <Table.Th scope="col">{t("batches.substance")}</Table.Th>
            <Table.Th scope="col">{t("batches.quantity")}</Table.Th>
            <Table.Th scope="col">{t("batches.parties")}</Table.Th>
            <Table.Th scope="col">{t("batches.approvedAt")}</Table.Th>
            <Table.Th scope="col">{t("batches.approvedBy")}</Table.Th>
            <Table.Th scope="col">{t("batches.flag")}</Table.Th>
            {canFlag && <Table.Th scope="col">{t("batches.actions")}</Table.Th>}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {items.map((item) => (
            <Table.Tr key={item.reference}>
              <Table.Td fw={600}>{item.reference}</Table.Td>
              <Table.Td>{item.substance}</Table.Td>
              <Table.Td>
                <Qty value={item.quantity} unit={item.unit} />
              </Table.Td>
              <Table.Td>{parties(item)}</Table.Td>
              <Table.Td>
                <DateText iso={item.approved_at} withTime />
              </Table.Td>
              <Table.Td>
                <ApprovedBy item={item} />
              </Table.Td>
              <Table.Td>
                <FlagText item={item} />
              </Table.Td>
              {canFlag && (
                <Table.Td>
                  {flaggable(item) && <FlagButton item={item} onFlag={onFlag} />}
                </Table.Td>
              )}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
