import { Alert, Button, PasswordInput, Stack, TextInput } from "@mantine/core";
import { useForm } from "@mantine/form";
import { useTranslation } from "react-i18next";
import { useStartLogin } from "@/api/hooks/auth";
import { signInError } from "./signInError";

interface Props {
  /** The user ID to start with (kept when coming back for a new code). */
  initialUserId: string;
  onChallenge: (challengeId: string, userId: string) => void;
}

// Step 1: user ID and password. The server answers with a challenge and sends a code by SMS.
export function PasswordStep({ initialUserId, onChallenge }: Props) {
  const { t } = useTranslation();
  const start = useStartLogin();
  const form = useForm({
    initialValues: { userId: initialUserId, password: "" },
    validate: {
      userId: (value) => (value.trim() ? null : t("signIn.userIdRequired")),
      password: (value) => (value ? null : t("signIn.passwordRequired")),
    },
  });

  const submit = form.onSubmit(({ userId, password }) => {
    const trimmed = userId.trim();
    start.mutate(
      { userId: trimmed, password },
      { onSuccess: ({ challenge_id }) => onChallenge(challenge_id, trimmed) },
    );
  });

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
}
