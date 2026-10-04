import { Card, Group, Text, Title } from "@mantine/core";
import { ACCENT_BORDER } from "@/theme";
import { ActionButton, type CardAction } from "./Action";

interface Props {
  title: string;
  /** One sentence. */
  body: string;
  action?: CardAction;
}

// The home page's "What's next": one sentence and one primary action, with a saffron left accent
// (a one-sided border, so square corners).
export function WhatsNextCard({ title, body, action }: Props) {
  return (
    <Card withBorder radius={0} padding="lg" style={{ borderLeft: ACCENT_BORDER }}>
      <Title order={2} size="h3">
        {title}
      </Title>
      <Text mt="xs">{body}</Text>
      {action && (
        <Group mt="md">
          <ActionButton action={action} />
        </Group>
      )}
    </Card>
  );
}
