import { ActionIcon, Indicator } from "@mantine/core";
import { IconBell } from "@tabler/icons-react";
import { useTranslation } from "react-i18next";
import { useHome } from "@/api/hooks/home";
import { useAlertsDrawer } from "./AlertsDrawerContext";

// The bell (personnel and the Head Authority): the unacknowledged alerts count, in saffron,
// refreshed with the home counts; it opens the alerts drawer.
export function Bell() {
  const { t } = useTranslation();
  const home = useHome();
  const drawer = useAlertsDrawer();
  const count = home.data?.counts.unacknowledged_alerts ?? 0;

  return (
    <Indicator
      label={<span aria-hidden>{count}</span>}
      disabled={count === 0}
      color="saffron"
      size={18}
      offset={4}
    >
      <ActionIcon
        variant="subtle"
        color="white"
        size="lg"
        onClick={drawer.open}
        aria-label={t("alerts.bell", { number: count })}
      >
        <IconBell aria-hidden />
      </ActionIcon>
    </Indicator>
  );
}
