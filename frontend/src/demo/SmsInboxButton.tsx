import { ActionIcon, Button } from "@mantine/core";
import { IconMessage2 } from "@tabler/icons-react";
import { useTranslation } from "react-i18next";
import { useDemo } from "./useDemo";

interface Props {
  /** In the navy header: an icon button. Elsewhere (sign-in, a code step): a text button. */
  variant: "header" | "text";
}

// Opens the demo SMS inbox. Renders nothing outside demo mode.
export function SmsInboxButton({ variant }: Props) {
  const { t } = useTranslation();
  const { enabled, openInbox } = useDemo();
  if (!enabled) return null;
  if (variant === "header") {
    return (
      <ActionIcon
        variant="subtle"
        color="white"
        size="lg"
        onClick={openInbox}
        aria-label={t("demo.inbox.open")}
      >
        <IconMessage2 aria-hidden />
      </ActionIcon>
    );
  }
  return (
    <Button
      variant="outline"
      leftSection={<IconMessage2 aria-hidden size={18} />}
      onClick={openInbox}
    >
      {t("demo.inbox.open")}
    </Button>
  );
}
