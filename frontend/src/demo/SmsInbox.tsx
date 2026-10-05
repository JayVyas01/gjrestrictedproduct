import { Button, Card, Drawer, Group, Stack, Text, VisuallyHidden } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useDemoInbox } from "@/api/hooks/demo";
import type { DemoInboxMessage } from "@/api/types";
import { DateText } from "@/components/DateText";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import type { CodeFill } from "./useDemo";

/** Read digit by digit ("1 5 9 9 0 0"), not as one large number. */
function spoken(code: string): string {
  return code.split("").join(" ");
}

/** The inbox's identity for a message (the API gives no ID). */
function messageKey(message: DemoInboxMessage): string {
  return `${message.created_at}|${message.contact_last4}|${message.code}`;
}

interface MessageProps {
  message: DemoInboxMessage;
  onUse: (code: string) => void;
}

function Message({ message, onUse }: MessageProps) {
  const { t } = useTranslation();
  const codeId = useId();
  return (
    <Card component="li" withBorder padding="sm">
      <Stack gap={4}>
        <Group justify="space-between" gap="xs" wrap="wrap">
          <Text fw={600}>{message.display_name}</Text>
          <Text size="sm">
            <span aria-hidden>••••{message.contact_last4}</span>
            <VisuallyHidden>{t("demo.inbox.to", { last4: message.contact_last4 })}</VisuallyHidden>
          </Text>
        </Group>
        <Text id={codeId} fz={32} fw={700} ff="monospace" lts={4}>
          <span aria-hidden>{message.code}</span>
          <VisuallyHidden>{t("demo.inbox.code", { code: spoken(message.code) })}</VisuallyHidden>
        </Text>
        <Group justify="space-between" gap="xs" wrap="wrap">
          <Text size="sm" c="gray.7">
            <DateText iso={message.created_at} withTime />
          </Text>
          <Button size="xs" onClick={() => onUse(message.code)} aria-describedby={codeId}>
            {t("demo.inbox.use")}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}

function Messages({ onUse }: { onUse: (code: string) => void }) {
  const { t } = useTranslation();
  const inbox = useDemoInbox();
  const newest = inbox.data?.[0];
  return (
    <Stack gap="sm">
      <Text size="sm" c="gray.7">
        {t("demo.inbox.intro")}
      </Text>
      {/* The newest code, announced when it changes (each poll that brings a new one). */}
      <VisuallyHidden role="status" aria-live="polite">
        {newest
          ? t("demo.inbox.newest", { code: spoken(newest.code), name: newest.display_name })
          : ""}
      </VisuallyHidden>
      {inbox.isPending ? (
        <LoadingSkeleton />
      ) : inbox.isError && !inbox.data ? (
        <ErrorNotice error={inbox.error} />
      ) : inbox.data.length === 0 ? (
        <Text>{t("demo.inbox.empty")}</Text>
      ) : (
        <Stack component="ul" gap="sm" p={0} m={0} style={{ listStyle: "none" }}>
          {inbox.data.map((message) => (
            <Message key={messageKey(message)} message={message} onUse={onUse} />
          ))}
        </Stack>
      )}
    </Stack>
  );
}

interface Props {
  opened: boolean;
  onClose: () => void;
  /** The code input on screen, if one has registered (see useDemoCodeFill). */
  codeFill: () => CodeFill | null;
}

// The demo SMS inbox: the codes the app "sent", newest first, refreshed every 3 seconds while
// open. "Use this code" fills the code input on screen (which then takes the focus), or copies
// the code when there is none. A modal drawer: titled, focus trapped, Escape closes.
export function SmsInbox({ opened, onClose, codeFill }: Props) {
  const { t } = useTranslation();
  // After "Use this code" the code input takes the focus, so it is not handed back to the opener.
  const [returnFocus, setReturnFocus] = useState(true);
  const [lastOpened, setLastOpened] = useState(opened);
  if (opened !== lastOpened) {
    setLastOpened(opened);
    if (opened) setReturnFocus(true);
  }

  const use = (code: string) => {
    const fill = codeFill();
    if (fill) {
      setReturnFocus(false);
      onClose();
      fill(code);
      return;
    }
    copy(code);
  };

  const copy = (code: string) => {
    const done = () => notifications.show({ message: t("demo.inbox.copied", { code }) });
    const failed = () => notifications.show({ message: t("demo.inbox.copyFailed", { code }) });
    if (!navigator.clipboard?.writeText) {
      failed();
      return;
    }
    navigator.clipboard.writeText(code).then(done, failed);
  };

  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      position="right"
      size="md"
      title={t("demo.inbox.title")}
      returnFocus={returnFocus}
      closeButtonProps={{ "aria-label": t("common.close") }}
    >
      {opened && <Messages onUse={use} />}
    </Drawer>
  );
}
