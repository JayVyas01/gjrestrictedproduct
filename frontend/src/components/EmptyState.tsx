import { Stack, Text, Title } from "@mantine/core";
import { ActionButton, type CardAction } from "./Action";

interface Props {
  title: string;
  body: string;
  action?: CardAction;
}

// What a list shows when it has nothing in it, with an optional way forward.
export function EmptyState({ title, body, action }: Props) {
  return (
    <Stack align="center" gap="xs" py="xl" ta="center">
      <Title order={2} size="h4">
        {title}
      </Title>
      <Text c="dimmed">{body}</Text>
      {action && <ActionButton action={action} />}
    </Stack>
  );
}
