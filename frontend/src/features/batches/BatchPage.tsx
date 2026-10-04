import { Anchor, Button, Card, Group, Stack, Text, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { useBatch, useRequestSignOffCode, useSignOff } from "@/api/hooks/oversight";
import type { BatchDetail, BatchItem } from "@/api/types";
import { CodeDialog } from "@/components/CodeDialog";
import { formatDate } from "@/components/DateText";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { Section } from "@/components/Section";
import { BatchStatusBadge } from "@/components/StatusBadge";
import { BatchItems } from "./BatchItems";
import { FlagDialog } from "./FlagDialog";
import { batchCounts, batchPeriod, signedLine } from "./period";

interface Props {
  /** The batch list (the back link). */
  listPath: string;
  /** No Flag or Sign off at all (the Head Authority and Software Owner views). */
  readOnly?: boolean;
}

function Summary({ batch }: { batch: BatchDetail }) {
  const { t } = useTranslation();
  const signed = signedLine(t, batch);
  return (
    <Card withBorder padding="md">
      <Stack gap={4}>
        <Group gap="xs">
          <Text fw={600}>{batch.position}</Text>
          <BatchStatusBadge status={batch.status} />
        </Group>
        <Text size="sm">{t("batches.dueOn", { date: formatDate(batch.due_on) })}</Text>
        <Text size="sm">{batchCounts(t, batch)}</Text>
        {signed && <Text size="sm">{signed}</Text>}
      </Stack>
    </Card>
  );
}

function SignOff({ batch }: { batch: BatchDetail }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const requestCode = useRequestSignOffCode();
  const signOff = useSignOff(batch.id);

  return (
    <Stack gap="sm" align="flex-start">
      <Text>{t("batches.signOffIntro")}</Text>
      <Button onClick={() => setOpen(true)}>{t("batches.signOff")}</Button>
      <CodeDialog
        opened={open}
        onClose={() => setOpen(false)}
        title={t("batches.signOffTitle")}
        requestCode={() => requestCode.mutateAsync(batch.id)}
        submit={({ challenge_id, code }) =>
          signOff.mutateAsync({ challengeId: challenge_id, code })
        }
        onDone={() => {
          setOpen(false);
          notifications.show({ message: t("batches.signedOff") });
        }}
      />
    </Stack>
  );
}

function Batch({ batch, readOnly }: { batch: BatchDetail; readOnly: boolean }) {
  const { t } = useTranslation();
  const [flagging, setFlagging] = useState<BatchItem | null>(null);
  // `can_sign` is false once signed and for anyone not holding the batch's position, and the
  // same holder is the only one who may flag.
  const reviewing = !readOnly && batch.can_sign;

  return (
    <>
      <Title order={1}>{t("batches.title", { period: batchPeriod(t, batch) })}</Title>
      <Summary batch={batch} />
      <Section title={t("batches.itemsTitle")}>
        {batch.items.length === 0 ? (
          <Text c="dimmed">{t("batches.noItems")}</Text>
        ) : (
          <BatchItems items={batch.items} canFlag={reviewing} onFlag={setFlagging} />
        )}
      </Section>
      {reviewing && <SignOff batch={batch} />}
      <FlagDialog batchId={batch.id} item={flagging} onClose={() => setFlagging(null)} />
    </>
  );
}

// One batch (`:id` in the path): its summary, the items table, Flag per item and Sign off for
// the superintendent holding the position. `readOnly` hides every action.
export function BatchPage({ listPath, readOnly = false }: Props) {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const batch = useBatch(Number(id));

  return (
    <Stack>
      <Anchor component={Link} to={listPath} size="sm">
        {t("batches.back")}
      </Anchor>
      {batch.isPending ? (
        <>
          <Title order={1}>{t("pages.batchDetail")}</Title>
          <LoadingSkeleton />
        </>
      ) : batch.isError ? (
        <>
          <Title order={1}>{t("pages.batchDetail")}</Title>
          <ErrorNotice error={batch.error} />
        </>
      ) : (
        <Batch batch={batch.data} readOnly={readOnly} />
      )}
    </Stack>
  );
}
