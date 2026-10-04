import { Skeleton, Stack } from "@mantine/core";
import { useTranslation } from "react-i18next";

interface Props {
  /** How many placeholder lines to draw (default 3). */
  lines?: number;
}

// What a page or a list shows while its data (or its code) loads: grey placeholder lines in
// the shape of content, announced once to screen readers as "Loading…".
export function LoadingSkeleton({ lines = 3 }: Props) {
  const { t } = useTranslation();
  return (
    <Stack gap="sm" role="status" aria-label={t("common.loading")} aria-busy="true">
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton key={index} height={index === 0 ? 28 : 18} width={index === 0 ? "40%" : "100%"} />
      ))}
    </Stack>
  );
}
