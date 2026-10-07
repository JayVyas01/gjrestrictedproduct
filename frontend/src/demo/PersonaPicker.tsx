import { Button, Paper, Stack, Text, Title } from "@mantine/core";
import { useId } from "react";
import { useTranslation } from "react-i18next";
import type { DemoPersona } from "@/api/types";
import { useDemo } from "./useDemo";

interface Props {
  /** Signs in as the persona: fills the form and submits it, as if typed. */
  onPick: (persona: DemoPersona) => void;
  disabled?: boolean;
}

function PersonaButton({ persona, onPick, disabled }: { persona: DemoPersona } & Props) {
  const descriptionId = useId();
  return (
    <Button
      variant="default"
      fullWidth
      h="auto"
      py="xs"
      justify="flex-start"
      disabled={disabled}
      onClick={() => onPick(persona)}
      aria-label={persona.label}
      aria-describedby={descriptionId}
      styles={{ label: { whiteSpace: "normal", textAlign: "left" } }}
    >
      <Stack gap={2} align="flex-start">
        <Text component="span" fw={700}>
          {persona.label}
        </Text>
        <Text component="span" size="sm" fw={400} id={descriptionId}>
          {persona.description}
        </Text>
      </Stack>
    </Button>
  );
}

// Demo mode only: one button per synthetic account. A click fills the role, the identifier (a
// GSTIN or an email) and the password and submits step 1, so the real password-and-code
// sign-in still runs.
export function PersonaPicker({ onPick, disabled }: Props) {
  const { t } = useTranslation();
  const { enabled, personas } = useDemo();
  const headingId = useId();
  if (!enabled || personas.length === 0) return null;
  return (
    <Paper component="section" withBorder p="lg" aria-labelledby={headingId}>
      <Stack gap="sm">
        <Title order={2} size="h4" id={headingId}>
          {t("demo.personas.title")}
        </Title>
        <Text size="sm" c="gray.7">
          {t("demo.personas.intro")}
        </Text>
        <Stack component="ul" gap="xs" p={0} m={0} style={{ listStyle: "none" }}>
          {personas.map((persona) => (
            <li key={persona.key}>
              <PersonaButton persona={persona} onPick={onPick} disabled={disabled} />
            </li>
          ))}
        </Stack>
      </Stack>
    </Paper>
  );
}
