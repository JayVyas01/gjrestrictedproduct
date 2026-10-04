import { Button, Group, Modal, Radio, Stack, TextInput } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useSaveReviewSetting } from "@/api/hooks/oversight";
import type { ReviewSetting } from "@/api/types";
import { ErrorNotice } from "@/components/ErrorNotice";

export const REVIEW_PERIOD_DAYS = [15, 30, 60] as const;

interface Props {
  /** The position being changed; null keeps the dialog closed. */
  setting: ReviewSetting | null;
  onClose: () => void;
}

// Changes one district position's review period: 15, 30 or 60 days, and an optional start date
// (a plain date input). A refusal (422) lists the server's reasons and keeps the dialog open.
export function ReviewPeriodDialog({ setting, onClose }: Props) {
  const { t } = useTranslation();
  const title = setting ? t("reviewPeriods.dialogTitle", { title: setting.title }) : "";
  return (
    <Modal
      opened={setting !== null}
      onClose={onClose}
      title={title}
      centered
      closeButtonProps={{ "aria-label": t("common.close") }}
    >
      {setting && <PeriodForm key={setting.position_id} setting={setting} onClose={onClose} />}
    </Modal>
  );
}

function PeriodForm({ setting, onClose }: { setting: ReviewSetting; onClose: () => void }) {
  const { t } = useTranslation();
  const save = useSaveReviewSetting();
  const [days, setDays] = useState(setting.period_days ? String(setting.period_days) : "");
  const [startsOn, setStartsOn] = useState("");
  const [missing, setMissing] = useState(false);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!days) {
      setMissing(true);
      return;
    }
    save.mutate(
      {
        positionId: setting.position_id,
        period: { period_days: Number(days), ...(startsOn ? { starts_on: startsOn } : {}) },
      },
      {
        onSuccess: () => {
          notifications.show({ message: t("reviewPeriods.saved") });
          onClose();
        },
      },
    );
  };

  return (
    <form onSubmit={submit} noValidate>
      <Stack>
        <ErrorNotice error={save.error} />
        <Radio.Group
          label={t("reviewPeriods.periodLabel")}
          value={days}
          onChange={(value) => {
            setDays(value);
            setMissing(false);
          }}
          error={missing ? t("reviewPeriods.periodRequired") : undefined}
          required
        >
          <Group gap="md" mt={4}>
            {REVIEW_PERIOD_DAYS.map((count) => (
              <Radio
                key={count}
                value={String(count)}
                label={t("reviewPeriods.days", { count })}
              />
            ))}
          </Group>
        </Radio.Group>
        <TextInput
          type="date"
          label={t("reviewPeriods.startLabel")}
          description={t("reviewPeriods.startHint")}
          value={startsOn}
          onChange={(event) => setStartsOn(event.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" loading={save.isPending}>
            {t("reviewPeriods.save")}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
