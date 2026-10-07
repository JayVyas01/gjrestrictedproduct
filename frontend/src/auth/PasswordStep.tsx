import { Alert, Button, PasswordInput, Radio, SimpleGrid, Stack, TextInput } from "@mantine/core";
import { useForm } from "@mantine/form";
import { forwardRef, useImperativeHandle } from "react";
import { useTranslation } from "react-i18next";
import { useStartLogin } from "@/api/hooks/auth";
import { SIGN_IN_ROLES, type LoginRole, type SignInRole } from "@/api/types";
import { GSTIN_FORMAT, isSignInRole, normaliseGstin, type SignInStart } from "./identifiers";
import { signInError } from "./signInError";

interface Props {
  initial: SignInStart;
  onChallenge: (challengeId: string, start: SignInStart) => void;
}

export interface PasswordStepHandle {
  /** The demo persona picker: fills every field and submits, exactly as if typed. */
  signInAs: (role: LoginRole, identifier: string, password: string) => void;
}

interface Values {
  role: SignInRole;
  identifier: string;
  password: string;
}

// Step 1: who is signing in (the role), their identifier (a party's GSTIN or an official's
// email) and the password. The server answers with a challenge and sends a code by SMS.
export const PasswordStep = forwardRef<PasswordStepHandle, Props>(function PasswordStep(
  { initial, onChallenge },
  ref,
) {
  const { t } = useTranslation();
  const start = useStartLogin();
  const form = useForm<Values>({
    initialValues: {
      role: initial.role,
      identifier: initial.identifier,
      password: "",
    },
    validate: {
      identifier: (value, values) => {
        const trimmed = value.trim();
        if (values.role === "PARTY") {
          if (!trimmed) return t("signIn.gstinRequired");
          return GSTIN_FORMAT.test(normaliseGstin(trimmed)) ? null : t("signIn.gstinInvalid");
        }
        return trimmed ? null : t("signIn.emailRequired");
      },
      password: (value) => (value ? null : t("signIn.passwordRequired")),
    },
  });
  const party = form.values.role === "PARTY";

  const send = ({ role, identifier, password }: Values) => {
    const trimmed = role === "PARTY" ? normaliseGstin(identifier) : identifier.trim();
    start.mutate(
      { role, identifier: trimmed, password },
      {
        onSuccess: ({ challenge_id }) => onChallenge(challenge_id, { role, identifier: trimmed }),
      },
    );
  };
  const submit = form.onSubmit(send);

  useImperativeHandle(ref, () => ({
    signInAs: (role, identifier, password) => {
      if (!isSignInRole(role)) return; // the Software Owner signs in through the API only
      const values = { role, identifier, password };
      form.setValues(values);
      form.clearErrors();
      if (!start.isPending) send(values);
    },
  }));

  const chooseRole = (value: string) => {
    if (!isSignInRole(value) || value === form.values.role) return;
    // A GSTIN is no email and the other way round: the identifier starts again.
    form.setValues({ role: value, identifier: "" });
    form.clearErrors();
    start.reset();
  };

  return (
    <form onSubmit={submit} noValidate>
      <Stack>
        {start.isError && (
          <Alert color="red" role="alert">
            {signInError(t, start.error, "password")}
          </Alert>
        )}
        {/* Native radios: one tab stop for the group, the arrow keys move between the roles. */}
        <Radio.Group
          label={t("signIn.roleLabel")}
          value={form.values.role}
          onChange={chooseRole}
          name="sign-in-role"
        >
          <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="xs" verticalSpacing="xs" mt="xs">
            {SIGN_IN_ROLES.map((role) => (
              <Radio key={role} value={role} label={t(`signIn.roles.${role}`)} />
            ))}
          </SimpleGrid>
        </Radio.Group>
        {party ? (
          <TextInput
            key="gstin"
            label={t("signIn.gstin")}
            description={t("signIn.gstinHelp")}
            autoComplete="username"
            autoCapitalize="characters"
            spellCheck={false}
            maxLength={15}
            required
            withAsterisk={false}
            {...form.getInputProps("identifier")}
            onChange={(event) =>
              form.setFieldValue("identifier", normaliseGstin(event.currentTarget.value))
            }
          />
        ) : (
          <TextInput
            key="email"
            type="email"
            label={t("signIn.email")}
            autoComplete="username"
            spellCheck={false}
            required
            withAsterisk={false}
            {...form.getInputProps("identifier")}
          />
        )}
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
