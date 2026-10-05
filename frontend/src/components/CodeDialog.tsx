import { Alert, Button, Group, Modal, PinInput, Stack, Text } from "@mantine/core";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import type { Challenge } from "@/api/types";
import { DemoCodeHint } from "@/demo/DemoCodeHint";
import { useDemo, useDemoCodeFill } from "@/demo/useDemo";
import { ErrorNotice } from "./ErrorNotice";
import { useFocusHeadingOnSuccess } from "./focusPageHeading";

const CODE_LENGTH = 6;
/** A code is valid for 5 minutes from when it was issued. */
export const CODE_LIFETIME_MS = 5 * 60_000;

export interface CodeSubmission {
  challenge_id: string;
  code: string;
}

interface Props<T> {
  opened: boolean;
  /** Escape, the close button or Cancel. */
  onClose: () => void;
  title: string;
  /** Sends an SMS code for this action (e.g. a decision-code endpoint). */
  requestCode: () => Promise<Challenge>;
  /** Carries out the action with the code. */
  submit: (input: CodeSubmission) => Promise<T>;
  onDone: (result: T) => void;
}

function minutesSeconds(ms: number): string {
  const total = Math.ceil(ms / 1000);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

// The one-time code step for a decision or sign-off, in a modal (focus trapped, Escape closes).
// Once the action is done its trigger is usually gone, so the page heading takes the focus.
export function CodeDialog<T>({ opened, onClose, title, onDone, ...rest }: Props<T>) {
  const { t } = useTranslation();
  const { returnFocus, succeed } = useFocusHeadingOnSuccess(opened);
  // Demo mode: Escape in the SMS inbox drawer (opened over this dialog) closes only the drawer.
  const { inboxOpen } = useDemo();
  const done = (result: T) => {
    succeed();
    onDone(result);
  };
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={title}
      centered
      returnFocus={returnFocus}
      closeOnEscape={!inboxOpen}
      closeButtonProps={{ "aria-label": t("common.close") }}
    >
      {opened && <CodeForm onClose={onClose} onDone={done} {...rest} />}
    </Modal>
  );
}

type FormProps<T> = Omit<Props<T>, "opened" | "title">;

function CodeForm<T>({ onClose, requestCode, submit, onDone }: FormProps<T>) {
  const { t } = useTranslation();
  const [challenge, setChallenge] = useState<{ id: string; issuedAt: number } | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [code, setCode] = useState("");
  const [requesting, setRequesting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [incomplete, setIncomplete] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const requested = useRef(false);
  const introId = useId();
  const errorId = useId();
  const pinId = useId();
  const submitButton = useRef<HTMLButtonElement>(null);

  // Demo mode: the SMS inbox's "Use this code" fills the digits; the user still confirms.
  useDemoCodeFill((filled) => {
    setCode(filled);
    setIncomplete(false);
    window.setTimeout(() => submitButton.current?.focus(), 0);
  });

  const sendCode = () => {
    setRequesting(true);
    setError(null);
    setCode("");
    setIncomplete(false);
    requestCode()
      .then(({ challenge_id }) => {
        const issuedAt = Date.now();
        setChallenge({ id: challenge_id, issuedAt });
        setNow(issuedAt);
      })
      .catch((failure: unknown) => {
        setChallenge(null);
        setError(failure);
      })
      .finally(() => setRequesting(false));
  };

  // One code per opening (the ref keeps StrictMode's second effect run from sending another).
  useEffect(() => {
    if (requested.current) return;
    requested.current = true;
    sendCode();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!challenge) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [challenge]);

  const remaining = challenge ? Math.max(0, challenge.issuedAt + CODE_LIFETIME_MS - now) : 0;
  const expired = challenge !== null && remaining === 0;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!challenge || expired) return;
    if (code.length !== CODE_LENGTH) {
      setIncomplete(true);
      return;
    }
    setSubmitting(true);
    setError(null);
    submit({ challenge_id: challenge.id, code })
      .then(onDone)
      .catch((failure: unknown) => {
        setError(failure);
        setCode("");
      })
      .finally(() => setSubmitting(false));
  };

  const wrongCode = error instanceof ApiError && error.status === 401;
  const message = expired
    ? t("code.expired")
    : wrongCode
      ? t("errors.wrongCode")
      : incomplete
        ? t("code.incomplete")
        : "";

  return (
    <form onSubmit={onSubmit} noValidate>
      <Stack>
        <Text id={introId}>{t("code.intro")}</Text>
        {message ? (
          <Alert color="red" role="alert" id={errorId}>
            {message}
          </Alert>
        ) : (
          <ErrorNotice error={error} />
        )}
        <div role="group" aria-label={t("code.label")} aria-describedby={introId}>
          <PinInput
            id={pinId}
            length={CODE_LENGTH}
            type="number"
            oneTimeCode
            value={code}
            onChange={(value) => {
              setCode(value);
              setIncomplete(false);
            }}
            error={Boolean(message)}
            // withAria off: Mantine's own aria attributes would overwrite aria-describedby.
            getInputProps={(index) => ({
              withAria: false,
              "aria-invalid": Boolean(message),
              "aria-label": t("code.digit", { position: index + 1 }),
              "aria-describedby": message ? errorId : undefined,
              "data-autofocus": index === 0 ? true : undefined,
            })}
          />
        </div>
        <Text size="sm" c="dimmed">
          {requesting
            ? t("code.requesting")
            : challenge && !expired
              ? t("code.expiresIn", { time: minutesSeconds(remaining) })
              : ""}
        </Text>
        <DemoCodeHint />
        <Group justify="space-between">
          <Button variant="subtle" onClick={sendCode} disabled={requesting || submitting}>
            {t("code.newCode")}
          </Button>
          <Group>
            <Button variant="default" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button
              ref={submitButton}
              type="submit"
              loading={submitting}
              disabled={!challenge || expired || requesting}
            >
              {t("code.submit")}
            </Button>
          </Group>
        </Group>
      </Stack>
    </form>
  );
}
