import { Button, Group, Modal, Stack, Text, Textarea } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useFlagItem } from "@/api/hooks/oversight";
import type { BatchItem } from "@/api/types";
import { ErrorNotice } from "@/components/ErrorNotice";
import { useFocusHeadingOnSuccess } from "@/components/focusPageHeading";
import {
  COMMENT_MAX,
  EMPTY_REASON,
  ReasonPicker,
  reasonComplete,
  type ReasonValue,
} from "@/components/ReasonPicker";

interface Props {
  batchId: number;
  /** The item being flagged; null keeps the dialog closed. */
  item: BatchItem | null;
  onClose: () => void;
}

// Flags one batch item: a superintendent-flag reason and a comment (required for Other, optional
// otherwise). A refusal (403: own approval, already flagged, signed) shows the server's text.
// Once flagged, the item's Flag button is gone, so the page heading takes the focus.
export function FlagDialog({ batchId, item, onClose }: Props) {
  const { t } = useTranslation();
  const { returnFocus, succeed } = useFocusHeadingOnSuccess(item !== null);
  const title = item ? t("batches.flagLabel", { reference: item.reference }) : "";
  const flagged = () => {
    succeed();
    onClose();
  };
  return (
    <Modal
      opened={item !== null}
      onClose={onClose}
      title={title}
      centered
      returnFocus={returnFocus}
      closeButtonProps={{ "aria-label": t("common.close") }}
    >
      {item && (
        <FlagForm
          key={item.reference}
          batchId={batchId}
          item={item}
          onClose={onClose}
          onFlagged={flagged}
        />
      )}
    </Modal>
  );
}

interface FormProps {
  batchId: number;
  item: BatchItem;
  onClose: () => void;
  onFlagged: () => void;
}

function FlagForm({ batchId, item, onClose, onFlagged }: FormProps) {
  const { t } = useTranslation();
  const flag = useFlagItem(batchId);
  const [reason, setReason] = useState<ReasonValue>(EMPTY_REASON);
  const [note, setNote] = useState("");
  const [showErrors, setShowErrors] = useState(false);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!reasonComplete(reason)) {
      setShowErrors(true);
      return;
    }
    const comment = (reason.needsComment ? reason.comment : note).trim();
    flag.mutate(
      { reference: item.reference, reason_code: reason.code, comment },
      {
        onSuccess: () => {
          notifications.show({ message: t("batches.flagged") });
          onFlagged();
        },
      },
    );
  };

  return (
    <form onSubmit={submit} noValidate>
      <Stack>
        <Text>{t("batches.flagIntro")}</Text>
        <ErrorNotice error={flag.error} />
        <ReasonPicker
          kind="SUPERINTENDENT_FLAG"
          value={reason}
          onChange={setReason}
          showErrors={showErrors}
        />
        {!reason.needsComment && (
          <Textarea
            label={t("batches.commentOptional")}
            description={t("batches.commentHint")}
            maxLength={COMMENT_MAX}
            autosize
            minRows={2}
            value={note}
            onChange={(event) => setNote(event.currentTarget.value)}
          />
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" color="red.9" loading={flag.isPending}>
            {t("batches.flagSubmit")}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
