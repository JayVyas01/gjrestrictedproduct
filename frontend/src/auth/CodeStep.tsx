import { Alert, Button, Group, PinInput, Stack, Text } from "@mantine/core";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useVerifyLogin } from "@/api/hooks/auth";
import { DemoCodeHint } from "@/demo/DemoCodeHint";
import { useDemoCodeFill } from "@/demo/useDemo";
import { clearDrafts, landingFor } from "./session";
import { signInError } from "./signInError";

const CODE_LENGTH = 6;

interface Props {
  challengeId: string;
  /** "Send a new code": back to step 1. */
  onRestart: () => void;
}

// Step 2: the six-digit code from the SMS (typed or pasted). On success, the role's home.
export function CodeStep({ challengeId, onRestart }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const verify = useVerifyLogin();
  const [code, setCode] = useState("");
  const [incomplete, setIncomplete] = useState(false);
  const digits = useRef<HTMLDivElement>(null);
  const introId = useId();
  const errorId = useId();
  // A fixed id: without one, PinInput swaps its generated id after mounting, which re-creates
  // the inputs and drops the focus set below.
  const pinId = useId();
  const submitButton = useRef<HTMLButtonElement>(null);

  // Demo mode: the SMS inbox's "Use this code" fills the digits; the user still presses Sign in.
  useDemoCodeFill((filled) => {
    setCode(filled);
    setIncomplete(false);
    window.setTimeout(() => submitButton.current?.focus(), 0);
  });

  // Focus moves to the first digit when this step appears, so the code can be pasted at once.
  useEffect(() => {
    digits.current?.querySelector<HTMLInputElement>("input:not([type=hidden])")?.focus();
  }, []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (code.length !== CODE_LENGTH) {
      setIncomplete(true);
      return;
    }
    // useVerifyLogin refetches `me` before this resolves, so the guard sees the new session.
    // A new session starts clean: no draft from an earlier one (whoever wrote it) carries over.
    verify.mutate(
      { challengeId, code },
      {
        onSuccess: ({ role }) => {
          clearDrafts();
          navigate(landingFor(role), { replace: true });
        },
      },
    );
  };

  const error = verify.isError
    ? signInError(t, verify.error, "code")
    : incomplete
      ? t("signIn.codeIncomplete")
      : "";

  return (
    <form onSubmit={submit} noValidate>
      <Stack>
        <Text id={introId}>{t("signIn.codeIntro")}</Text>
        {error && (
          <Alert color="red" role="alert" id={errorId}>
            {error}
          </Alert>
        )}
        <div ref={digits} role="group" aria-label={t("signIn.code")} aria-describedby={introId}>
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
            error={Boolean(error)}
            // withAria off: Mantine's own aria attributes would overwrite aria-describedby.
            getInputProps={(index) => ({
              withAria: false,
              "aria-invalid": Boolean(error),
              "aria-label": t("signIn.codeDigit", { position: index + 1 }),
              "aria-describedby": error ? errorId : undefined,
            })}
          />
        </div>
        <DemoCodeHint />
        <Group justify="space-between">
          <Button variant="subtle" onClick={onRestart}>
            {t("signIn.newCode")}
          </Button>
          <Button ref={submitButton} type="submit" loading={verify.isPending}>
            {t("signIn.submit")}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
