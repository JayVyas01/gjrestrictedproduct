import { Stack, Text, Title } from "@mantine/core";
import { useTranslation } from "react-i18next";
import type en from "@/i18n/en.json";

export type PageKey = Exclude<keyof typeof en.pages, "comingSoon">;

// Stands in for a screen a later task builds, so its route exists and is guarded already.
export function PlaceholderPage({ title }: { title: PageKey }) {
  const { t } = useTranslation();
  return (
    <Stack>
      <Title order={1}>{t(`pages.${title}`)}</Title>
      <Text c="dimmed">{t("pages.comingSoon")}</Text>
    </Stack>
  );
}
