import { Container, Paper, Stack, Text, Title } from "@mantine/core";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { CodeStep } from "./CodeStep";
import { PasswordStep } from "./PasswordStep";

// Sign-in: user ID and password, then the code sent by SMS. The challenge stays in memory only
// (never in the URL). `?expired=1` explains why the user is here again.
export function SignInPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const [userId, setUserId] = useState("");
  const [challengeId, setChallengeId] = useState<string | null>(null);

  return (
    <Container component="main" id="main" size={420} py="xl">
      <Stack>
        <Text fw={600} c="navy.6">
          {t("app.name")}
        </Text>
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
              initialUserId={userId}
              onChallenge={(challenge, id) => {
                setUserId(id);
                setChallengeId(challenge);
              }}
            />
          )}
        </Paper>
      </Stack>
    </Container>
  );
}
