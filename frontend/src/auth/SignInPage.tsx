import { Container, Group, Paper, Stack, Text, Title } from "@mantine/core";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { DemoRibbon } from "@/demo/DemoRibbon";
import { PersonaPicker } from "@/demo/PersonaPicker";
import { SmsInboxButton } from "@/demo/SmsInboxButton";
import { CodeStep } from "./CodeStep";
import { PasswordStep, type PasswordStepHandle } from "./PasswordStep";

// Sign-in: user ID and password, then the code sent by SMS. The challenge stays in memory only
// (never in the URL). `?expired=1` explains why the user is here again. In demo mode only: the
// demo ribbon, the SMS inbox button and, on step 1, the persona picker.
export function SignInPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const [userId, setUserId] = useState("");
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
              initialUserId={userId}
              onChallenge={(challenge, id) => {
                setUserId(id);
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
                passwordStep.current?.signInAs(persona.identifier, persona.password)
              }
            />
            <Group>
              <SmsInboxButton variant="text" />
            </Group>
          </>
        )}
      </Stack>
    </Container>
  );
}
