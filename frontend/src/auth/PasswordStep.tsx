import { Alert, Button, PasswordInput, Stack, TextInput } from "@mantine/core";
import { useForm } from "@mantine/form";
import { forwardRef, useImperativeHandle } from "react";
import { useTranslation } from "react-i18next";
import { useStartLogin } from "@/api/hooks/auth";
import { signInError } from "./signInError";

interface Props {
  /** The user ID to start with (kept when coming back for a new code). */
  initialUserId: string;
  onChallenge: (challengeId: string, userId: string) => void;
}

export interface PasswordStepHandle {
  /** The demo persona picker: fills both fields and submits, exactly as if typed. */
  signInAs: (userId: string, password: string) => void;
}

// Step 1: user ID and password. The server answers with a challenge and sends a code by SMS.
export const PasswordStep = forwardRef<PasswordStepHandle, Props>(function PasswordStep(
  { initialUserId, onChallenge },
  ref,
) {
  const { t } = useTranslation();
  const start = useStartLogin();
  const form = useForm({
    initialValues: { userId: initialUserId, password: "" },
    validate: {
      userId: (value) => (value.trim() ? null : t("signIn.userIdRequired")),
      password: (value) => (value ? null : t("signIn.passwordRequired")),
    },
  });

  const send = ({ userId, password }: { userId: string; password: string }) => {
    const trimmed = userId.trim();
    start.mutate(
      { userId: trimmed, password },
      { onSuccess: ({ challenge_id }) => onChallenge(challenge_id, trimmed) },
    );
  };
  const submit = form.onSubmit(send);

  useImperativeHandle(ref, () => ({
    signInAs: (userId, password) => {
      const values = { userId, password };
      form.setValues(values);
      if (!start.isPending) send(values);
    },
  }));

  return (
    <form onSubmit={submit} noValidate>
      <Stack>
        {start.isError && (
          <Alert color="red" role="alert">
            {signInError(t, start.error, "password")}
          </Alert>
        )}
        <TextInput
          label={t("signIn.userId")}
          autoComplete="username"
          required
          withAsterisk={false}
          {...form.getInputProps("userId")}
        />
        <PasswordInput
          label={t("signIn.password")}
          autoComplete="current-password"
          required
          withAsterisk={false}
          {...form.getInputProps("password")}
        />
        <Button type="submit" loading={start.isPending}>
          {t("common.continue")}
        </Button>
      </Stack>
    </form>
  );
});
