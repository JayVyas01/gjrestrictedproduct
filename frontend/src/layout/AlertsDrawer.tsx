import {
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  Drawer,
  Group,
  Loader,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ApiError } from "@/api/client";
import { useAcknowledgeAlert, useAlerts } from "@/api/hooks/alerts";
import { invalidate, keys } from "@/api/hooks/keys";
import type { Alert, Role } from "@/api/types";
import { useSession } from "@/auth/SessionProvider";
import { DateText } from "@/components/DateText";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { COMMENT_MAX } from "@/components/ReasonPicker";
import { Qty } from "@/components/Qty";
import { ACCENT_BORDER } from "@/theme";

/** Where an alert's reference links to, for roles with a transaction screen (fixed paths). */
const TRANSACTIONS_FOR: Partial<Record<Role, string>> = {
  PERSONNEL: "/personnel/transactions",
};

/** A buyer-rejection pattern of 2 or more is a repeat, and is highlighted. */
const REPEAT_FROM = 2;

interface ItemProps {
  alert: Alert;
  /** Only personnel hold positions, so only they can acknowledge (the server checks the holder). */
  canAcknowledge: boolean;
  transactionsPath: string | undefined;
  onNavigate: () => void;
}

function AcknowledgeForm({ alert, onDone }: { alert: Alert; onDone: () => void }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const acknowledge = useAcknowledgeAlert();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");

  const submit = () =>
    acknowledge.mutate(
      { id: alert.id, note: note.trim() },
      {
        onSuccess: () => {
          notifications.show({ message: t("alerts.done") });
          onDone();
        },
        onError: (error) => {
          // Someone else acknowledged it first: show the alert as it now is.
          if (error instanceof ApiError && error.status === 409) {
            void invalidate(client, keys.alerts);
          }
        },
      },
    );

  return (
    <Stack gap="xs">
      <ErrorNotice error={acknowledge.error} />
      {!alert.acknowledged &&
        (open ? (
          <>
            <Textarea
              label={t("alerts.note")}
              description={t("alerts.noteHint")}
              maxLength={COMMENT_MAX}
              autosize
              minRows={2}
              value={note}
              onChange={(event) => setNote(event.currentTarget.value)}
              data-autofocus
            />
            <Group>
              <Button onClick={submit} loading={acknowledge.isPending}>
                {t("alerts.confirm")}
              </Button>
              <Button
                variant="default"
                onClick={() => {
                  setOpen(false);
                  acknowledge.reset();
                }}
              >
                {t("common.cancel")}
              </Button>
            </Group>
          </>
        ) : (
          <Group>
            <Button variant="outline" onClick={() => setOpen(true)}>
              {t("alerts.acknowledge")}
            </Button>
          </Group>
        ))}
    </Stack>
  );
}

function AlertItem({ alert, canAcknowledge, transactionsPath, onNavigate }: ItemProps) {
  const { t } = useTranslation();
  const [formKey, setFormKey] = useState(0);
  const repeat = (alert.pattern_count ?? 0) >= REPEAT_FROM;
  const reference = alert.transaction_reference;

  return (
    <Card component="li" withBorder padding="md">
      <Stack gap={6}>
        <Group justify="space-between" gap="xs" wrap="wrap">
          <Title order={3} size="h5">
            {alert.kind_label}
          </Title>
          {alert.acknowledged && (
            <Badge color="gray.7" variant="filled" tt="none">
              {t("alerts.acknowledged")}
            </Badge>
          )}
        </Group>
        <Text size="sm" c="dimmed">
          {t("alerts.raised")} <DateText iso={alert.created_at} withTime />
        </Text>
        <Text size="sm">
          {t("alerts.reference")}{" "}
          {transactionsPath ? (
            <Anchor
              component={Link}
              to={`${transactionsPath}/${encodeURIComponent(reference)}`}
              onClick={onNavigate}
              fw={600}
            >
              {reference}
            </Anchor>
          ) : (
            <Text component="span" fw={600}>
              {reference}
            </Text>
          )}
        </Text>
        <Text size="sm">
          {alert.substance}, <Qty value={alert.quantity} unit={alert.unit} />
        </Text>
        <Text size="sm">
          {t("transactions.between", { seller: alert.seller_name, buyer: alert.buyer_name })}
        </Text>
        <Text size="sm">{t("alerts.reason", { reason: alert.reason })}</Text>
        {alert.comment && (
          <Text size="sm">{t("alerts.comment", { comment: alert.comment })}</Text>
        )}
        {alert.pattern && (
          <Box
            data-repeat={repeat ? "true" : "false"}
            p={repeat ? "xs" : 0}
            bg={repeat ? "saffron.0" : undefined}
            style={repeat ? { borderLeft: ACCENT_BORDER } : undefined}
          >
            <Group gap="xs" wrap="wrap">
              {repeat && (
                <Badge color="saffron.5" variant="filled" tt="none">
                  {t("alerts.repeat")}
                </Badge>
              )}
              <Text size="sm" fw={repeat ? 600 : undefined}>
                {alert.pattern}
              </Text>
            </Group>
          </Box>
        )}
        {alert.acknowledged && alert.acknowledged_at && (
          <Text size="sm" c="dimmed">
            {t("alerts.acknowledged")} <DateText iso={alert.acknowledged_at} withTime />
          </Text>
        )}
        {alert.note && <Text size="sm">{t("alerts.acknowledgedNote", { note: alert.note })}</Text>}
        {canAcknowledge && (
          <AcknowledgeForm
            key={formKey}
            alert={alert}
            onDone={() => setFormKey((key) => key + 1)}
          />
        )}
      </Stack>
    </Card>
  );
}

function AlertsList({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { user } = useSession();
  const alerts = useAlerts();
  if (alerts.isPending) return <Loader size="sm" role="status" aria-label={t("common.loading")} />;
  if (alerts.isError) return <ErrorNotice error={alerts.error} />;
  if (alerts.data.alerts.length === 0) {
    return <EmptyState title={t("alerts.empty")} body={t("alerts.emptyBody")} />;
  }
  const canAcknowledge = user?.role === "PERSONNEL";
  const transactionsPath = user ? TRANSACTIONS_FOR[user.role] : undefined;

  return (
    <Stack gap="sm">
      {!canAcknowledge && (
        <Text size="sm" c="dimmed">
          {t("alerts.readOnly")}
        </Text>
      )}
      <Stack component="ul" gap="sm" p={0} m={0} style={{ listStyle: "none" }}>
        {alerts.data.alerts.map((alert) => (
          <AlertItem
            key={alert.id}
            alert={alert}
            canAcknowledge={canAcknowledge}
            transactionsPath={transactionsPath}
            onNavigate={onClose}
          />
        ))}
      </Stack>
    </Stack>
  );
}

// The alerts from the bell, as the server orders them (unacknowledged first): kind, reference,
// goods, parties, reason, comment and the buyer-rejection pattern (highlighted when repeated),
// with "Acknowledge" and an optional note. A modal drawer: titled, focus trapped, Escape closes.
export function AlertsDrawer({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      position="right"
      size="md"
      title={t("alerts.title")}
      closeButtonProps={{ "aria-label": t("common.close") }}
    >
      {opened && <AlertsList onClose={onClose} />}
    </Drawer>
  );
}
