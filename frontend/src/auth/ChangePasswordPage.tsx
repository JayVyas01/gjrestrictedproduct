import {
  Alert,
  Button,
  Center,
  Container,
  Group,
  List,
  Loader,
  Paper,
  PasswordInput,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import { useChangePassword } from "@/api/hooks/auth";
import { DemoRibbon } from "@/demo/DemoRibbon";
import { MIN_PASSWORD_LENGTH } from "./identifiers";
import { landingFor } from "./session";
import { useSession } from "./SessionProvider";
import { signInError } from "./signInError";

const RULES = ["length", "numeric", "common", "different"] as const;

interface Values {
  current: string;
  next: string;
  confirm: string;
}

/** The server's field names → this form's. */
const FIELDS: Record<string, keyof Values> = {
  current_password: "current",
  new_password: "next",
};

/**
 * The server's 400 as field errors on this form, or null when it named no field of it
 * (shown in the alert instead).
 */
function fieldErrorsOf(error: unknown): Partial<Record<keyof Values, string>> | null {
  if (!(error instanceof ApiError) || !error.fieldErrors) return null;
  const errors: Partial<Record<keyof Values, string>> = {};
  for (const [field, messages] of Object.entries(error.fieldErrors)) {
    const name = FIELDS[field];
    if (name && messages.length) errors[name] = messages.join(" ");
  }
  return Object.keys(errors).length ? errors : null;
}

// Choosing a new password: required while `me.must_change_password` is set (a password the
// system issued, owner decision A3: RequireRole and the 403 `password_change_required` both
// send the user here), and open to any signed-in user. Outside the app shell, since nothing else
// answers until the password is changed. On success `me` is fetched again, then the role's home.
export function ChangePasswordPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, loading, signOut } = useSession();
  const change = useChangePassword();
  const form = useForm<Values>({
    initialValues: { current: "", next: "", confirm: "" },
    validate: {
      current: (value) => (value ? null : t("changePassword.currentRequired")),
      next: (value) => {
        if (!value) return t("changePassword.newRequired");
        return value.length < MIN_PASSWORD_LENGTH ? t("changePassword.tooShort") : null;
      },
      confirm: (value, values) => {
        if (!value) return t("changePassword.confirmRequired");
        return value === values.next ? null : t("changePassword.mismatch");
      },
    },
  });

  if (loading) {
    return (
      <Center mih="50vh">
        <Loader role="status" aria-label={t("common.loading")} />
      </Center>
    );
  }
  if (!user) return <Navigate to="/sign-in" replace />;

  const submit = form.onSubmit(({ current, next }) => {
    change.mutate(
      { current_password: current, new_password: next },
      {
        // useChangePassword refetches `me` first, so the guards see the flag cleared.
        onSuccess: () => navigate(landingFor(user.role), { replace: true }),
        onError: (error) => {
          const errors = fieldErrorsOf(error);
          if (errors) form.setErrors(errors);
        },
      },
    );
  });
  const fieldErrors = change.isError && fieldErrorsOf(change.error);
  const alert = change.isError && !fieldErrors ? signInError(t, change.error, "password") : "";

  return (
    <Container component="main" id="main" size={420} py="xl">
      <Stack>
        <Group justify="space-between" gap="xs" wrap="wrap">
          <Text fw={600} c="navy.6">
            {t("app.name")}
          </Text>
          <DemoRibbon />
        </Group>
        <Title order={1}>{t("changePassword.title")}</Title>
        <Text>
          {user.must_change_password ? t("changePassword.issuedIntro") : t("changePassword.intro")}
        </Text>
        <Paper withBorder p="lg">
          <form onSubmit={submit} noValidate>
            <Stack>
              {alert && (
                <Alert color="red" role="alert">
                  {alert}
                </Alert>
              )}
              <div>
                <Text fw={600} size="sm">
                  {t("changePassword.rulesTitle")}
                </Text>
                <List size="sm" spacing={2}>
                  {RULES.map((rule) => (
                    <List.Item key={rule}>{t(`changePassword.rules.${rule}`)}</List.Item>
                  ))}
                </List>
              </div>
              <PasswordInput
                label={t("changePassword.current")}
                autoComplete="current-password"
                required
                withAsterisk={false}
                {...form.getInputProps("current")}
              />
              <PasswordInput
                label={t("changePassword.new")}
                autoComplete="new-password"
                required
                withAsterisk={false}
                {...form.getInputProps("next")}
              />
              <PasswordInput
                label={t("changePassword.confirm")}
                autoComplete="new-password"
                required
                withAsterisk={false}
                {...form.getInputProps("confirm")}
              />
              <Group justify="space-between">
                <Button variant="subtle" onClick={() => void signOut()}>
                  {t("session.signOut")}
                </Button>
                <Button type="submit" loading={change.isPending}>
                  {t("changePassword.submit")}
                </Button>
              </Group>
            </Stack>
          </form>
        </Paper>
      </Stack>
    </Container>
  );
}
