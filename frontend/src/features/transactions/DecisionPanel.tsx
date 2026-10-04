import { Button, Group, Stack, Text } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import { invalidate, keys } from "@/api/hooks/keys";
import { useDecideTransaction, useRequestDecisionCode } from "@/api/hooks/transactions";
import type { Decision } from "@/api/transactions";
import type { Outcome, ReasonKind, TransactionDetail, ViewerRole } from "@/api/types";
import { CodeDialog, type CodeSubmission } from "@/components/CodeDialog";
import { ErrorNotice } from "@/components/ErrorNotice";
import {
  EMPTY_REASON,
  ReasonPicker,
  reasonComplete,
  type ReasonValue,
} from "@/components/ReasonPicker";

/** The reasons a rejection is given from: the buyer's own list, or the officers'. */
export function reasonKindFor(role: ViewerRole): ReasonKind {
  return role === "buyer" ? "BUYER_REJECTION" : "OFFICER_REJECTION";
}

const STOCK_LIMIT_REASON: ReasonValue = { code: "STOCK_LIMIT", comment: "", needsComment: false };

/**
 * The outcomes to offer: exactly the server's `allowed_outcomes`, except that a buyer over their
 * stock limit is offered Reject only, whatever else was listed.
 */
export function offeredOutcomes(tx: TransactionDetail): Outcome[] {
  if (!tx.can_decide) return [];
  if (tx.your_role === "buyer" && tx.stock_limit_problem) {
    return tx.allowed_outcomes.filter((outcome) => outcome === "REJECT");
  }
  return tx.allowed_outcomes;
}

// A refusal that means the transaction changed under the viewer: shown on the page, not in the
// code dialog, and the transaction is fetched again.
function isRefusal(error: unknown): error is ApiError {
  return error instanceof ApiError && (error.status === 422 || error.status === 409);
}

interface Props {
  transaction: TransactionDetail;
}

// The viewer's decision, driven only by the server's `allowed_outcomes` (and `can_decide`, which
// the parent checks). Each outcome is confirmed with a one-time code; Reject first asks for a
// reason. Over the stock limit, the buyer sees the reject form at once with STOCK_LIMIT chosen.
export function DecisionPanel({ transaction }: Props) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const { reference } = transaction;
  const requestCode = useRequestDecisionCode();
  const decide = useDecideTransaction(reference);

  const outcomes = offeredOutcomes(transaction);
  const stockLimit = transaction.your_role === "buyer" && Boolean(transaction.stock_limit_problem);
  const canReject = outcomes.includes("REJECT");
  const [rejecting, setRejecting] = useState(stockLimit && canReject);
  const [reason, setReason] = useState<ReasonValue>(stockLimit ? STOCK_LIMIT_REASON : EMPTY_REASON);
  const [showErrors, setShowErrors] = useState(false);
  const [pending, setPending] = useState<Outcome | null>(null);
  const [refusal, setRefusal] = useState<unknown>(null);

  if (outcomes.length === 0) return null;

  const open = (outcome: Outcome) => {
    setRefusal(null);
    setPending(outcome);
  };

  const continueReject = () => {
    if (!reasonComplete(reason)) {
      setShowErrors(true);
      return;
    }
    open("REJECT");
  };

  const decision = (outcome: Outcome, { challenge_id, code }: CodeSubmission): Decision =>
    outcome === "REJECT"
      ? { challenge_id, code, outcome, reason_code: reason.code, comment: reason.comment.trim() }
      : { challenge_id, code, outcome };

  const submit = (input: CodeSubmission) => {
    const outcome = pending ?? "REJECT";
    return decide.mutateAsync(decision(outcome, input)).then(
      () => outcome,
      (error: unknown) => {
        if (isRefusal(error)) {
          setRefusal(error);
          setPending(null);
          void invalidate(client, keys.transactions);
        }
        throw error;
      },
    );
  };

  const done = (outcome: Outcome) => {
    setPending(null);
    setRejecting(stockLimit && canReject);
    notifications.show({ message: t(`transaction.done.${outcome}`) });
  };

  return (
    <Stack gap="md">
      <ErrorNotice error={refusal} />
      {!rejecting && (
        <Group>
          {outcomes.map((outcome) => (
            <Button
              key={outcome}
              color={outcome === "REJECT" ? "red.9" : undefined}
              variant={outcome === "REJECT" ? "outline" : "filled"}
              onClick={() => (outcome === "REJECT" ? setRejecting(true) : open(outcome))}
            >
              {t(`transaction.outcome.${outcome}`)}
            </Button>
          ))}
        </Group>
      )}
      {rejecting && (
        <Stack gap="sm">
          <Text fw={600}>{t("transaction.rejectTitle")}</Text>
          <ReasonPicker
            kind={reasonKindFor(transaction.your_role)}
            value={reason}
            onChange={setReason}
            showCodes={stockLimit ? ["STOCK_LIMIT"] : []}
            showErrors={showErrors}
          />
          <Group>
            <Button color="red.9" onClick={continueReject}>
              {t("transaction.continueReject")}
            </Button>
            {!stockLimit && (
              <Button
                variant="default"
                onClick={() => {
                  setRejecting(false);
                  setShowErrors(false);
                }}
              >
                {t("common.back")}
              </Button>
            )}
          </Group>
        </Stack>
      )}
      <CodeDialog
        opened={pending !== null}
        onClose={() => setPending(null)}
        title={t(`transaction.dialog.${pending ?? "REJECT"}`)}
        requestCode={() => requestCode.mutateAsync(reference)}
        submit={submit}
        onDone={done}
      />
    </Stack>
  );
}
