import { Text } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { SAFFRON } from "@/theme";
import { useDemo } from "./useDemo";

// "DEMO — synthetic data": a plain tag (not a control) in the header and on sign-in, so no one
// mistakes the demo for the live service. Saffron outline, navy text on white (AA).
export function DemoRibbon() {
  const { t } = useTranslation();
  const { enabled } = useDemo();
  if (!enabled) return null;
  return (
    <Text
      component="span"
      size="xs"
      fw={700}
      c="navy.8"
      bg="white"
      px={8}
      py={2}
      style={{ border: `2px solid ${SAFFRON}`, borderRadius: 4, whiteSpace: "nowrap" }}
    >
      {t("demo.ribbon")}
    </Text>
  );
}
