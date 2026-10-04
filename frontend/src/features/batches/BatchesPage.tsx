import { Anchor, Card, Group, Stack, Text, Title } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useBatches } from "@/api/hooks/oversight";
import { formatDate } from "@/components/DateText";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { BatchStatusBadge } from "@/components/StatusBadge";
import { BATCHES_PATH } from "@/features/personnel/paths";
import { batchCounts, batchPeriod, signedLine } from "./period";

interface Props {
  /** Each card links to `${basePath}/${id}` (the superintendent's list by default). */
  basePath?: string;
}

// The batches the viewer may see, newest period first as served: one card each with the period
// (linked), the position, the due date, the status and the item and flag counts. Read-only by
// nature, so the Head Authority and the Software Owner can reuse it under their own path.
export function BatchesPage({ basePath = BATCHES_PATH }: Props) {
  const { t } = useTranslation();
  const batches = useBatches();

  return (
    <Stack>
      <Title order={1}>{t("pages.batches")}</Title>
      {batches.isPending ? (
        <LoadingSkeleton />
      ) : batches.isError ? (
        <ErrorNotice error={batches.error} />
      ) : batches.data.length === 0 ? (
        <EmptyState title={t("batches.empty")} body={t("batches.emptyBody")} />
      ) : (
        <Stack
          component="ul"
          gap="sm"
          p={0}
          m={0}
          aria-label={t("batches.list")}
          style={{ listStyle: "none" }}
        >
          {batches.data.map((batch) => {
            const signed = signedLine(t, batch, false);
            return (
              <Card component="li" key={batch.id} withBorder padding="md">
                <Group justify="space-between" wrap="wrap" gap="xs">
                  <Title order={2} size="h4">
                    <Anchor component={Link} to={`${basePath}/${batch.id}`}>
                      {batchPeriod(t, batch)}
                    </Anchor>
                  </Title>
                  <BatchStatusBadge status={batch.status} />
                </Group>
                <Text mt="xs">{batch.position}</Text>
                <Text size="sm">{t("batches.dueOn", { date: formatDate(batch.due_on) })}</Text>
                <Text size="sm">{batchCounts(t, batch)}</Text>
                {signed && (
                  <Text size="sm" c="dimmed">
                    {signed}
                  </Text>
                )}
              </Card>
            );
          })}
        </Stack>
      )}
    </Stack>
  );
}
