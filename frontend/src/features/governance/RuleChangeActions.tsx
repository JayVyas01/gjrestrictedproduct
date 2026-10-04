import { Button, Group, Modal, Stack, Text, Textarea } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import {
  useDecideRuleChange,
  useRequestRuleChangeCode,
  useWithdrawRuleChange,
} from "@/api/hooks/governance";
import { invalidate, keys } from "@/api/hooks/keys";
import type { RuleChange } from "@/api/types";
import { CodeDialog, type CodeSubmission } from "@/components/CodeDialog";
import { ErrorNotice } from "@/components/ErrorNotice";
import { useFocusHeadingOnSuccess } from "@/components/focusPageHeading";

/** Same as DecideSerializer: a rejection needs a note of 10 to 500 characters. */
export const NOTE_MIN = 10;
export const NOTE_MAX = 500;

type Outcome = "APPROVE" | "REJECT";

// A refusal that means the change moved on (already decided, or no longer valid): shown on the
// page, not in the code dialog, and the change is fetched again.
function isRefusal(error: unknown): error is ApiError {
  return error instanceof ApiError && (error.status === 409 || error.status === 422);
}

// "Withdraw", for the drafter while the change is open: asks for confirmation first. Once
// withdrawn the button goes away, so the page heading takes the focus.
export function WithdrawRuleChange({ id }: { id: number }) {
  const { t } = useTranslation();
  const withdraw = useWithdrawRuleChange(id);
  const [opened, setOpened] = useState(false);
  const { returnFocus, succeed } = useFocusHeadingOnSuccess(opened);
  const close = () => setOpened(false);
  const confirm = () =>
    withdraw.mutate(undefined, {
      onSuccess: () => {
        succeed();
        close();
        notifications.show({ message: t("ruleChange.withdrawn") });
      },
    });

  return (
    <>
      <Group>
        <Button
          variant="outline"
          color="red.9"
          onClick={() => {
            withdraw.reset();
            setOpened(true);
          }}
        >
          {t("ruleChange.withdraw")}
        </Button>
      </Group>
      <Modal
        opened={opened}
        onClose={close}
        title={t("ruleChange.withdrawTitle")}
        centered
        returnFocus={returnFocus}
        closeButtonProps={{ "aria-label": t("common.close") }}
      >
        <Stack>
          <Text>{t("ruleChange.withdrawBody")}</Text>
          <ErrorNotice error={withdraw.error} />
          <Group justify="flex-end">
            <Button variant="default" onClick={close} data-autofocus>
              {t("ruleChange.keep")}
            </Button>
            <Button color="red.9" onClick={confirm} loading={withdraw.isPending}>
              {t("ruleChange.withdrawConfirm")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}

// Approve or reject, for a Head Authority officer who did not draft the change (`can_decide`).
// Rejecting asks for a note of at least 10 characters first; both go through the code dialog.
export function DecideRuleChange({ change }: { change: RuleChange }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const requestCode = useRequestRuleChangeCode();
  const decide = useDecideRuleChange(change.id);
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [noteError, setNoteError] = useState<string | null>(null);
  const [pending, setPending] = useState<Outcome | null>(null);
  const [refusal, setRefusal] = useState<unknown>(null);

  const open = (outcome: Outcome) => {
    setRefusal(null);
    setPending(outcome);
  };

  const continueReject = () => {
    const length = note.trim().length;
    if (length < NOTE_MIN || length > NOTE_MAX) {
      setNoteError(t("ruleChange.noteLength"));
      return;
    }
    open("REJECT");
  };

  const submit = ({ challenge_id, code }: CodeSubmission) => {
    const outcome = pending ?? "REJECT";
    const decision =
      outcome === "REJECT"
        ? { challenge_id, code, outcome, note: note.trim() }
        : { challenge_id, code, outcome };
    return decide.mutateAsync(decision).then(
      () => outcome,
      (error: unknown) => {
        if (isRefusal(error)) {
          setRefusal(error);
          setPending(null);
          void invalidate(client, keys.ruleChanges);
        }
        throw error;
      },
    );
  };

  const done = (outcome: Outcome) => {
    setPending(null);
    setRejecting(false);
    notifications.show({ message: t(`ruleChange.done.${outcome}`) });
  };

  return (
    <Stack gap="md">
      <ErrorNotice error={refusal} />
      {!rejecting ? (
        <Group>
          <Button onClick={() => open("APPROVE")}>{t("ruleChange.approve")}</Button>
          <Button color="red.9" variant="outline" onClick={() => setRejecting(true)}>
            {t("ruleChange.reject")}
          </Button>
        </Group>
      ) : (
        <Stack gap="sm">
          <Textarea
            label={t("ruleChange.rejectNote")}
            description={t("ruleChange.rejectNoteHint")}
            value={note}
            maxLength={NOTE_MAX}
            autosize
            minRows={2}
            required
            withAsterisk={false}
            error={noteError}
            onChange={(event) => {
              setNote(event.currentTarget.value);
              setNoteError(null);
            }}
          />
          <Group>
            <Button color="red.9" onClick={continueReject}>
              {t("ruleChange.continueReject")}
            </Button>
            <Button
              variant="default"
              onClick={() => {
                setRejecting(false);
                setNoteError(null);
              }}
            >
              {t("common.back")}
            </Button>
          </Group>
        </Stack>
      )}
      <CodeDialog
        opened={pending !== null}
        onClose={() => setPending(null)}
        title={t(`ruleChange.dialog.${pending ?? "APPROVE"}`)}
        requestCode={() => requestCode.mutateAsync(change.id)}
        submit={submit}
        onDone={done}
      />
    </Stack>
  );
}
