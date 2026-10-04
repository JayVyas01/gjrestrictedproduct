import { Button, Stack, Table, Text, Title } from "@mantine/core";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useReviewSettings } from "@/api/hooks/oversight";
import type { ReviewSetting } from "@/api/types";
import { DateText } from "@/components/DateText";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { ReviewPeriodDialog } from "./ReviewPeriodDialog";

interface Props {
  /** No Change button (the Head Authority and Software Owner views). */
  readOnly?: boolean;
}

function Period({ setting }: { setting: ReviewSetting }) {
  const { t } = useTranslation();
  if (setting.period_days === null) return <span>{t("common.notSet")}</span>;
  return <span>{t("reviewPeriods.days", { count: setting.period_days })}</span>;
}

// Every district superintendent position with its review period, start, current period end and
// last batch. The Licensing Authority changes a period through a dialog; the Head Authority and
// the Software Owner see the same table read-only.
export function ReviewPeriodsPage({ readOnly = false }: Props) {
  const { t } = useTranslation();
  const settings = useReviewSettings();
  const [changing, setChanging] = useState<ReviewSetting | null>(null);

  return (
    <Stack>
      <Title order={1}>{t("pages.reviewPeriods")}</Title>
      <Text>{t("reviewPeriods.intro")}</Text>
      {readOnly && <Text c="dimmed">{t("reviewPeriods.readOnly")}</Text>}
      {settings.isPending ? (
        <LoadingSkeleton />
      ) : settings.isError ? (
        <ErrorNotice error={settings.error} />
      ) : settings.data.length === 0 ? (
        <EmptyState title={t("reviewPeriods.empty")} body={t("reviewPeriods.emptyBody")} />
      ) : (
        <Table.ScrollContainer minWidth={720}>
          <Table striped aria-label={t("reviewPeriods.table")}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th scope="col">{t("reviewPeriods.position")}</Table.Th>
                <Table.Th scope="col">{t("reviewPeriods.period")}</Table.Th>
                <Table.Th scope="col">{t("reviewPeriods.startsOn")}</Table.Th>
                <Table.Th scope="col">{t("reviewPeriods.periodEnd")}</Table.Th>
                <Table.Th scope="col">{t("reviewPeriods.lastBatch")}</Table.Th>
                {!readOnly && <Table.Th scope="col">{t("reviewPeriods.actions")}</Table.Th>}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {settings.data.map((setting) => (
                <Table.Tr key={setting.position_id}>
                  <Table.Td>{setting.title}</Table.Td>
                  <Table.Td>
                    <Period setting={setting} />
                  </Table.Td>
                  <Table.Td>
                    <DateText iso={setting.starts_on} />
                  </Table.Td>
                  <Table.Td>
                    <DateText iso={setting.current_period_end} />
                  </Table.Td>
                  <Table.Td>
                    {setting.last_batch_end ? (
                      <DateText iso={setting.last_batch_end} />
                    ) : (
                      t("reviewPeriods.noBatch")
                    )}
                  </Table.Td>
                  {!readOnly && (
                    <Table.Td>
                      <Button
                        size="xs"
                        variant="light"
                        aria-label={t("reviewPeriods.changeLabel", { title: setting.title })}
                        onClick={() => setChanging(setting)}
                      >
                        {t("reviewPeriods.change")}
                      </Button>
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {!readOnly && <ReviewPeriodDialog setting={changing} onClose={() => setChanging(null)} />}
    </Stack>
  );
}
