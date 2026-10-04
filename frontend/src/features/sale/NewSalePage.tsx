import { Alert, Button, Group, Stack, Stepper, Text, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import type { TransactionDetail } from "@/api/types";
import { LICENSEE_HOME_PATH, TRANSACTIONS_PATH } from "@/features/licensee/paths";
import { BuyerStep } from "./BuyerStep";
import { clearDraft, emptyDraft, loadDraft, saveDraft, type SaleDraft } from "./draft";
import { GoodsStep } from "./GoodsStep";
import { ReviewStep } from "./ReviewStep";
import { TransportStep } from "./TransportStep";
import { reachableStep, stepErrors, type FieldErrors } from "./validation";

const STEPS = ["buyer", "goods", "transport", "review"] as const;
/** The draft is written this long after the last change. */
export const DRAFT_DEBOUNCE_MS = 300;

/** The draft this tab saved, on the furthest step that still holds; or a fresh one. */
function initialDraft(): { draft: SaleDraft; restored: boolean } {
  const saved = loadDraft();
  if (!saved) return { draft: emptyDraft(), restored: false };
  return { draft: { ...saved, step: reachableStep(saved) }, restored: true };
}

// The new-sale wizard: buyer, goods (with a live check), transport, then review and send.
// The draft lives in this tab's sessionStorage only, and is cleared once the sale is sent.
export function NewSalePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [initial] = useState(initialDraft);
  const [draft, setDraft] = useState<SaleDraft>(initial.draft);
  const [restored, setRestored] = useState(initial.restored);
  const [errors, setErrorState] = useState<FieldErrors>({});
  const headingId = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const shownStep = useRef(draft.step);
  // Set by a change the seller made; a sent or discarded sale is never saved again.
  const dirty = useRef(false);
  const finished = useRef(false);

  const update = useCallback((patch: Partial<SaleDraft>) => {
    dirty.current = true;
    setDraft((current) => ({ ...current, ...patch }));
  }, []);
  const setErrors = useCallback(
    (patch: FieldErrors) => setErrorState((current) => ({ ...current, ...patch })),
    [],
  );

  // Save after a pause in typing; a pending save is dropped when the page goes away.
  useEffect(() => {
    if (!dirty.current || finished.current) return;
    const timer = window.setTimeout(() => {
      if (!finished.current) saveDraft(draft);
    }, DRAFT_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [draft]);

  // A new step: its heading takes the focus, so screen readers announce where the seller is.
  useEffect(() => {
    if (shownStep.current === draft.step) return;
    shownStep.current = draft.step;
    heading.current?.focus();
  }, [draft.step]);

  const goTo = (step: number) => {
    setErrorState({});
    update({ step });
  };

  const next = () => {
    const found = stepErrors(draft.step, draft);
    setErrorState(found);
    if (Object.keys(found).length === 0) goTo(draft.step + 1);
  };

  const startOver = () => {
    clearDraft();
    dirty.current = false;
    setErrorState({});
    setDraft(emptyDraft());
    setRestored(false);
  };

  const discard = () => {
    finished.current = true;
    clearDraft();
    navigate(LICENSEE_HOME_PATH);
  };

  const sent = (transaction: TransactionDetail) => {
    finished.current = true;
    clearDraft();
    notifications.show({ color: "green", message: t("sale.sent") });
    navigate(`${TRANSACTIONS_PATH}/${encodeURIComponent(transaction.reference)}`);
  };

  const stepProps = { draft, update, errors, setErrors };
  const current = STEPS[draft.step] ?? "buyer";

  return (
    <Stack maw={720}>
      <Title order={1}>{t("sale.title")}</Title>

      {restored && (
        <Alert color="blue" title={t("sale.draftRestored")}>
          <Stack gap="xs">
            <Text size="sm">{t("sale.draftRestoredBody")}</Text>
            <Group>
              <Button size="xs" variant="default" onClick={startOver}>
                {t("sale.startOver")}
              </Button>
              <Button size="xs" variant="subtle" color="red.9" onClick={discard}>
                {t("sale.discardDraft")}
              </Button>
            </Group>
          </Stack>
        </Alert>
      )}

      <Stepper
        active={draft.step}
        onStepClick={(step) => step < draft.step && goTo(step)}
        allowNextStepsSelect={false}
        size="sm"
      >
        {STEPS.map((step) => (
          <Stepper.Step key={step} label={t(`sale.steps.${step}`)} />
        ))}
      </Stepper>
      <Text fw={700}>{t("sale.progress", { current: draft.step + 1, total: STEPS.length })}</Text>

      <Stack component="section" aria-labelledby={headingId}>
        <Title order={2} id={headingId} ref={heading} tabIndex={-1}>
          {t(`sale.steps.${current}`)}
        </Title>
        {current === "buyer" && <BuyerStep {...stepProps} />}
        {current === "goods" && <GoodsStep {...stepProps} />}
        {current === "transport" && <TransportStep {...stepProps} />}
        {current === "review" && (
          <ReviewStep
            draft={draft}
            onSent={sent}
            onChangeGoods={() => {
              update({ check: null });
              goTo(1);
            }}
          />
        )}
      </Stack>

      <Group>
        {draft.step > 0 && (
          <Button variant="default" onClick={() => goTo(draft.step - 1)}>
            {t("sale.back")}
          </Button>
        )}
        {current !== "review" && <Button onClick={next}>{t("sale.next")}</Button>}
      </Group>
    </Stack>
  );
}
