import { Alert, Button, Group, List, Stack, Table, Text } from "@mantine/core";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import { useSubstances } from "@/api/hooks/catalogue";
import type { NewSale } from "@/api/transactions";
import type { TransactionDetail } from "@/api/types";
import { useStartSale } from "@/api/hooks/transactions";
import { ErrorNotice } from "@/components/ErrorNotice";
import { Qty } from "@/components/Qty";
import type { SaleDraft } from "./draft";
import { TwoStepNotice } from "./GoodsStep";

/** The POST body for the draft, tidied. */
export function toNewSale(draft: SaleDraft): NewSale {
  return {
    buyer_gstin: draft.gstin,
    substance_code: draft.substanceCode,
    quantity: draft.quantity.trim(),
    transporter_name: draft.transporterName.trim(),
    transporter_id_number: draft.transporterId.trim(),
    vehicle_number: draft.vehicleNumber.trim().toUpperCase(),
    route: draft.route.trim(),
  };
}

interface Props {
  draft: SaleDraft;
  onSent: (transaction: TransactionDetail) => void;
  /** Back to step 2 after a refusal. */
  onChangeGoods: () => void;
}

// Step 4: everything on one page, then "Send to buyer".
export function ReviewStep({ draft, onSent, onChangeGoods }: Props) {
  const { t } = useTranslation();
  const substances = useSubstances();
  const send = useStartSale();
  const substance = substances.data?.find((s) => s.code === draft.substanceCode);
  const sale = toNewSale(draft);
  const error = send.error;
  const fieldMessages =
    error instanceof ApiError && error.fieldErrors ? Object.values(error.fieldErrors).flat() : [];

  const rows: [string, ReactNode][] = [
    [t("transaction.buyer"), draft.buyerName],
    [t("sale.gstinShort"), sale.buyer_gstin],
    [t("transaction.substance"), substance?.name ?? sale.substance_code],
    [
      t("transaction.quantity"),
      <Qty key="qty" value={sale.quantity} unit={substance?.unit ?? null} />,
    ],
    [t("transaction.transporter"), sale.transporter_name],
    [t("transaction.transporterId"), sale.transporter_id_number],
    [t("transaction.vehicle"), sale.vehicle_number],
    [t("transaction.route"), sale.route],
  ];

  return (
    <Stack>
      <Text>{t("sale.reviewIntro")}</Text>
      <Table withTableBorder bg="white" maw={560}>
        <Table.Tbody>
          {rows.map(([label, value]) => (
            <Table.Tr key={label}>
              <Table.Th scope="row" w="40%">
                {label}
              </Table.Th>
              <Table.Td>{value}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <TwoStepNotice draft={draft} />

      {error && (
        <Stack gap="xs">
          <ErrorNotice error={error} />
          {fieldMessages.length > 0 && (
            <Alert color="red">
              <List size="sm">
                {fieldMessages.map((message) => (
                  <List.Item key={message}>{message}</List.Item>
                ))}
              </List>
            </Alert>
          )}
          {error instanceof ApiError && error.status === 422 && (
            <Group>
              <Button variant="subtle" px={0} onClick={onChangeGoods}>
                {t("sale.changeGoods")}
              </Button>
            </Group>
          )}
        </Stack>
      )}

      <Group>
        <Button onClick={() => send.mutate(sale, { onSuccess: onSent })} loading={send.isPending}>
          {t("sale.send")}
        </Button>
      </Group>
    </Stack>
  );
}
