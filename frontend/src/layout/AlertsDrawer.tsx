import { Drawer, Text } from "@mantine/core";
import { useTranslation } from "react-i18next";

// The alerts list from the bell. Task 7 fills it with /api/alerts and acknowledging.
export function AlertsDrawer({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      position="right"
      title={t("alerts.title")}
      closeButtonProps={{ "aria-label": t("common.close") }}
    >
      <Text c="dimmed">{t("alerts.comingSoon")}</Text>
    </Drawer>
  );
}
