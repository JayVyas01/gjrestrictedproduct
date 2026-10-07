import {
  Alert,
  Anchor,
  Button,
  Center,
  Container,
  Group,
  Loader,
  Paper,
  PasswordInput,
  PinInput,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import {
  useCompleteDemoSignup,
  useDemoSignupCandidates,
  useStartDemoSignup,
} from "@/api/hooks/demo";
import type { DemoSignupCandidate, DemoSignupForm } from "@/api/types";
import { DemoCodeHint } from "@/demo/DemoCodeHint";
import { DemoRibbon } from "@/demo/DemoRibbon";
import { SmsInboxButton } from "@/demo/SmsInboxButton";
import { useDemo, useDemoCodeFill } from "@/demo/useDemo";
import { GSTIN_FORMAT, MIN_PASSWORD_LENGTH, normaliseGstin, type SignInStart } from "./identifiers";
import { signInError } from "./signInError";

const CODE_LENGTH = 6;
/** At least 10 digits; spaces, dashes and a leading "+" allowed (as the server checks). */
const PHONE_FORMAT = /^\+?[\d\s-]{10,20}$/;
/** Enough to catch a typo; the server checks the address properly. */
const EMAIL_FORMAT = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface Values {
  gstin: string;
  phone: string;
  email: string;
  businessName: string;
  address: string;
  password: string;
  confirm: string;
}

/** The server's field names → this form's. */
const FIELDS: Record<string, keyof Values> = {
  gstin: "gstin",
  phone: "phone",
  email: "email",
  business_name: "businessName",
  address: "address",
  password: "password",
};

function fieldErrorsOf(error: unknown): Partial<Record<keyof Values, string>> | null {
  if (!(error instanceof ApiError) || !error.fieldErrors) return null;
  const errors: Partial<Record<keyof Values, string>> = {};
  for (const [field, messages] of Object.entries(error.fieldErrors)) {
    const name = FIELDS[field];
    if (name && messages.length) errors[name] = messages.join(" ");
  }
  return Object.keys(errors).length ? errors : null;
}

// "Pick a demo business": licensed businesses with no account yet. A pick fills the GSTIN, the
// phone on file and the business name; the tester still types the rest.
function CandidatePicker({ onPick }: { onPick: (candidate: DemoSignupCandidate) => void }) {
  const { t } = useTranslation();
  const candidates = useDemoSignupCandidates();
  const headingId = useId();
  if (!candidates.isSuccess) return null;
  return (
    <Paper component="section" withBorder p="lg" aria-labelledby={headingId}>
      <Stack gap="sm">
        <Title order={2} size="h4" id={headingId}>
          {t("signUp.pick.title")}
        </Title>
        <Text size="sm" c="gray.7">
          {candidates.data.length ? t("signUp.pick.intro") : t("signUp.pick.none")}
        </Text>
        <Stack component="ul" gap="xs" p={0} m={0} style={{ listStyle: "none" }}>
          {candidates.data.map((candidate) => (
            <li key={candidate.gstin}>
              <Button
                variant="default"
                fullWidth
                h="auto"
                py="xs"
                justify="flex-start"
                onClick={() => onPick(candidate)}
                styles={{ label: { whiteSpace: "normal", textAlign: "left" } }}
              >
                <Stack gap={2} align="flex-start">
                  <Text component="span" fw={700}>
                    {t("signUp.pick.use", { name: candidate.business_name })}
                  </Text>
                  <Text component="span" size="sm" fw={400}>
                    {t("signUp.pick.details", {
                      gstin: candidate.gstin,
                      phone: candidate.phone_on_file,
                    })}
                  </Text>
                </Stack>
              </Button>
            </li>
          ))}
        </Stack>
      </Stack>
    </Paper>
  );
}

function DetailsStep({
  onChallenge,
}: {
  onChallenge: (challengeId: string, gstin: string) => void;
}) {
  const { t } = useTranslation();
  const start = useStartDemoSignup();
  const firstField = useRef<HTMLInputElement>(null);
  const form = useForm<Values>({
    initialValues: {
      gstin: "",
      phone: "",
      email: "",
      businessName: "",
      address: "",
      password: "",
      confirm: "",
    },
    validate: {
      gstin: (value) => {
        if (!value.trim()) return t("signUp.gstinRequired");
        return GSTIN_FORMAT.test(normaliseGstin(value)) ? null : t("signUp.gstinInvalid");
      },
      phone: (value) => {
        if (!value.trim()) return t("signUp.phoneRequired");
        return PHONE_FORMAT.test(value.trim()) ? null : t("signUp.phoneInvalid");
      },
      email: (value) => {
        if (!value.trim()) return t("signUp.emailRequired");
        return EMAIL_FORMAT.test(value.trim()) ? null : t("signUp.emailInvalid");
      },
      businessName: (value) => (value.trim() ? null : t("signUp.businessNameRequired")),
      address: (value) => (value.trim() ? null : t("signUp.addressRequired")),
      password: (value) => {
        if (!value) return t("signUp.passwordRequired");
        return value.length < MIN_PASSWORD_LENGTH ? t("signUp.tooShort") : null;
      },
      confirm: (value, values) => {
        if (!value) return t("signUp.confirmRequired");
        return value === values.password ? null : t("signUp.mismatch");
      },
    },
  });

  const pick = (candidate: DemoSignupCandidate) => {
    form.setValues({
      gstin: candidate.gstin,
      phone: candidate.phone_on_file,
      businessName: candidate.business_name,
    });
    form.clearErrors();
    start.reset();
    firstField.current?.focus();
  };

  const submit = form.onSubmit((values) => {
    const body: DemoSignupForm = {
      gstin: normaliseGstin(values.gstin),
      phone: values.phone.trim(),
      email: values.email.trim(),
      business_name: values.businessName.trim(),
      address: values.address.trim(),
      password: values.password,
    };
    start.mutate(body, {
      onSuccess: ({ challenge_id }) => onChallenge(challenge_id, body.gstin),
      onError: (error) => {
        const errors = fieldErrorsOf(error);
        if (errors) form.setErrors(errors);
      },
    });
  });
  const fieldErrors = start.isError && fieldErrorsOf(start.error);
  // A 401 is the server's one answer for every mismatch: shown as it is.
  const alert = start.isError && !fieldErrors ? signInError(t, start.error, "password") : "";

  return (
    <>
      <Paper withBorder p="lg">
        <form onSubmit={submit} noValidate>
          <Stack>
            {alert && (
              <Alert color="red" role="alert">
                {alert}
              </Alert>
            )}
            <TextInput
              ref={firstField}
              label={t("signUp.gstin")}
              description={t("signUp.gstinHelp")}
              autoCapitalize="characters"
              spellCheck={false}
              maxLength={15}
              required
              withAsterisk={false}
              {...form.getInputProps("gstin")}
              onChange={(event) =>
                form.setFieldValue("gstin", normaliseGstin(event.currentTarget.value))
              }
            />
            <TextInput
              type="tel"
              label={t("signUp.phone")}
              description={t("signUp.phoneHelp")}
              autoComplete="tel"
              required
              withAsterisk={false}
              {...form.getInputProps("phone")}
            />
            <TextInput
              type="email"
              label={t("signUp.email")}
              autoComplete="email"
              spellCheck={false}
              required
              withAsterisk={false}
              {...form.getInputProps("email")}
            />
            <TextInput
              label={t("signUp.businessName")}
              autoComplete="organization"
              required
              withAsterisk={false}
              {...form.getInputProps("businessName")}
            />
            <Textarea
              label={t("signUp.address")}
              autoComplete="street-address"
              autosize
              minRows={2}
              required
              withAsterisk={false}
              {...form.getInputProps("address")}
            />
            <PasswordInput
              label={t("signUp.password")}
              description={t("signUp.passwordHelp")}
              autoComplete="new-password"
              required
              withAsterisk={false}
              {...form.getInputProps("password")}
            />
            <PasswordInput
              label={t("signUp.confirm")}
              autoComplete="new-password"
              required
              withAsterisk={false}
              {...form.getInputProps("confirm")}
            />
            <Button type="submit" loading={start.isPending}>
              {t("signUp.submit")}
            </Button>
          </Stack>
        </form>
      </Paper>
      <CandidatePicker onPick={pick} />
    </>
  );
}

// The code sent to the phone on file, as on sign-in's code step (demo: "Use this code" fills it).
function CodeStep({
  challengeId,
  onDone,
  onRestart,
}: {
  challengeId: string;
  onDone: () => void;
  onRestart: () => void;
}) {
  const { t } = useTranslation();
  const complete = useCompleteDemoSignup();
  const [code, setCode] = useState("");
  const [incomplete, setIncomplete] = useState(false);
  const digits = useRef<HTMLDivElement>(null);
  const submitButton = useRef<HTMLButtonElement>(null);
  const introId = useId();
  const errorId = useId();
  const pinId = useId();

  useDemoCodeFill((filled) => {
    setCode(filled);
    setIncomplete(false);
    window.setTimeout(() => submitButton.current?.focus(), 0);
  });

  useEffect(() => {
    digits.current?.querySelector<HTMLInputElement>("input:not([type=hidden])")?.focus();
  }, []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (code.length !== CODE_LENGTH) {
      setIncomplete(true);
      return;
    }
    complete.mutate({ challengeId, code }, { onSuccess: onDone });
  };

  const error = complete.isError
    ? signInError(t, complete.error, "code")
    : incomplete
      ? t("signIn.codeIncomplete")
      : "";

  return (
    <Paper withBorder p="lg">
      <form onSubmit={submit} noValidate>
        <Stack>
          <Text id={introId}>{t("signUp.codeIntro")}</Text>
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
            <Button ref={submitButton} type="submit" loading={complete.isPending}>
              {t("signUp.createAccount")}
            </Button>
          </Group>
        </Stack>
      </form>
    </Paper>
  );
}

function Done({ gstin }: { gstin: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);
  // Router state, never the URL: sign-in preselects Party and fills the GSTIN.
  const state: SignInStart = { role: "PARTY", identifier: gstin };
  return (
    <Paper withBorder p="lg">
      <Stack>
        <Title order={2} size="h4" ref={heading} tabIndex={-1}>
          {t("signUp.doneTitle")}
        </Title>
        <Text>{t("signUp.done", { gstin })}</Text>
        <Group>
          <Button onClick={() => navigate("/sign-in", { state })}>{t("signUp.goSignIn")}</Button>
        </Group>
      </Stack>
    </Paper>
  );
}

type Step =
  | { name: "details" }
  | { name: "code"; challengeId: string; gstin: string }
  | {
      name: "done";
      gstin: string;
    };

// Demo only (owner decision A4): a licensed business signs up through its GSTIN, proving it
// with the code sent to the phone on file of its licence (A5). The details, then the code, then
// "sign in as Party with GSTIN …". Outside demo mode (the persona list answers 404) this page
// sends the visitor to sign-in. The challenge stays in memory only, never in the URL.
export function SignUpPage() {
  const { t } = useTranslation();
  const demo = useDemo();
  const [step, setStep] = useState<Step>({ name: "details" });

  if (demo.loading) {
    return (
      <Center mih="50vh">
        <Loader role="status" aria-label={t("common.loading")} />
      </Center>
    );
  }
  if (!demo.enabled) return <Navigate to="/sign-in" replace />;

  return (
    <Container component="main" id="main" size={480} py="xl">
      <Stack>
        <Group justify="space-between" gap="xs" wrap="wrap">
          <Text fw={600} c="navy.6">
            {t("app.name")}
          </Text>
          <DemoRibbon />
        </Group>
        <Title order={1}>{t("signUp.title")}</Title>
        {step.name === "details" && (
          <>
            <Text>{t("signUp.intro")}</Text>
            <DetailsStep
              onChallenge={(challengeId, gstin) => setStep({ name: "code", challengeId, gstin })}
            />
          </>
        )}
        {step.name === "code" && (
          <CodeStep
            challengeId={step.challengeId}
            onDone={() => setStep({ name: "done", gstin: step.gstin })}
            onRestart={() => setStep({ name: "details" })}
          />
        )}
        {step.name === "done" && <Done gstin={step.gstin} />}
        {step.name !== "done" && (
          <Text>
            {t("signUp.haveAccount")}{" "}
            <Anchor component={Link} to="/sign-in">
              {t("signUp.signIn")}
            </Anchor>
          </Text>
        )}
        {/* The code step has its own way into the inbox (DemoCodeHint). */}
        {step.name === "details" && (
          <Group>
            <SmsInboxButton variant="text" />
          </Group>
        )}
      </Stack>
    </Container>
  );
}
