import { Anchor, Container, Group, Paper, Stack, Text, Title } from "@mantine/core";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { DemoRibbon } from "@/demo/DemoRibbon";
import { PersonaPicker } from "@/demo/PersonaPicker";
import { SmsInboxButton } from "@/demo/SmsInboxButton";
import { useDemo } from "@/demo/useDemo";
import { CodeStep } from "./CodeStep";
import { signInStartFrom, type SignInStart } from "./identifiers";
import { PasswordStep, type PasswordStepHandle } from "./PasswordStep";

/** Step 1 starts as a party unless sign-up's router state says otherwise. */
const DEFAULT_START: SignInStart = { role: "PARTY", identifier: "" };

// Sign-in: the role, its identifier (a GSTIN or an email) and the password, then the code sent
// by SMS. The challenge stays in memory only (never in the URL). `?expired=1` explains why the
// user is here again; sign-up's router state preselects Party and the new GSTIN. In demo mode
// only: the demo ribbon, the SMS inbox button and, on step 1, the persona picker and the link
// to sign-up.
export function SignInPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const location = useLocation();
  const demo = useDemo();
  const [start, setStart] = useState<SignInStart>(
    () => signInStartFrom(location.state) ?? DEFAULT_START,
  );
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const passwordStep = useRef<PasswordStepHandle>(null);

  return (
    <Container component="main" id="main" size={420} py="xl">
      <Stack>
        <Group justify="space-between" gap="xs" wrap="wrap">
          <Text fw={600} c="navy.6">
            {t("app.name")}
          </Text>
          <DemoRibbon />
        </Group>
        <Title order={1}>{t("signIn.title")}</Title>
        {params.get("expired") === "1" && (
          // Mantine's Alert always has role="alert"; this notice is polite, so it is a status.
          <Paper role="status" withBorder p="sm" bg="navy.0">
            <Text>{t("signIn.expired")}</Text>
          </Paper>
        )}
        <Paper withBorder p="lg">
          {challengeId ? (
            <CodeStep challengeId={challengeId} onRestart={() => setChallengeId(null)} />
          ) : (
            <PasswordStep
              ref={passwordStep}
              initial={start}
              onChallenge={(challenge, started) => {
                setStart(started);
                setChallengeId(challenge);
              }}
            />
          )}
        </Paper>
        {/* The code step has its own way into the inbox (DemoCodeHint). */}
        {!challengeId && (
          <>
            <PersonaPicker
              onPick={(persona) =>
                passwordStep.current?.signInAs(persona.role, persona.identifier, persona.password)
              }
            />
            {demo.enabled && (
              <Text>
                {t("signIn.newBusiness")}{" "}
                <Anchor component={Link} to="/sign-up">
                  {t("signIn.signUp")}
                </Anchor>
              </Text>
            )}
            <Group>
              <SmsInboxButton variant="text" />
            </Group>
          </>
        )}
      </Stack>
    </Container>
  );
}
