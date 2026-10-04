import { Button, Group, Modal, Stack, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useCancelTransaction } from "@/api/hooks/transactions";
import type { TransactionDetail } from "@/api/types";
import { ErrorNotice } from "@/components/ErrorNotice";

/** Only the seller, and only while the sale waits for the buyer. */
export function canCancel(tx: TransactionDetail): boolean {
  return tx.your_role === "seller" && tx.status === "AWAITING_BUYER";
}

// "Cancel sale": asks for confirmation, then cancels and says so.
export function CancelSale({ reference }: { reference: string }) {
  const { t } = useTranslation();
  const cancel = useCancelTransaction(reference);
  const [opened, setOpened] = useState(false);

  const close = () => setOpened(false);
  const confirm = () =>
    cancel.mutate(undefined, {
      onSuccess: () => {
        close();
        notifications.show({ message: t("transaction.cancelled") });
      },
    });

  return (
    <>
      <Group>
        <Button
          variant="outline"
          color="red.9"
          onClick={() => {
            cancel.reset();
            setOpened(true);
          }}
        >
          {t("transaction.cancelSale")}
        </Button>
      </Group>
      <Modal
        opened={opened}
        onClose={close}
        title={t("transaction.cancelTitle")}
        centered
        closeButtonProps={{ "aria-label": t("common.close") }}
      >
        <Stack>
          <Text>{t("transaction.cancelBody")}</Text>
          <ErrorNotice error={cancel.error} />
          <Group justify="flex-end">
            <Button variant="default" onClick={close} data-autofocus>
              {t("transaction.keepSale")}
            </Button>
            <Button color="red.9" onClick={confirm} loading={cancel.isPending}>
              {t("transaction.cancelConfirm")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
