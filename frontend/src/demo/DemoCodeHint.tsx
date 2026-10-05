import { Group, Text } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { SmsInboxButton } from "./SmsInboxButton";
import { useDemo } from "./useDemo";

// Under a code input in demo mode: where the code is, and a way to open the inbox.
export function DemoCodeHint() {
  const { t } = useTranslation();
  const { enabled } = useDemo();
  if (!enabled) return null;
  return (
    <Group justify="space-between" gap="xs" wrap="wrap">
      <Text size="sm">{t("demo.codeHint")}</Text>
      <SmsInboxButton variant="text" />
    </Group>
  );
}
