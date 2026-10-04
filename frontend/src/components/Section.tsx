import { Stack, Title } from "@mantine/core";
import { useId, type ReactNode } from "react";
import { ErrorNotice } from "./ErrorNotice";
import { LoadingSkeleton } from "./LoadingSkeleton";

// A titled page section (a region named by its heading), as on the home pages.
export function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return (
    <Stack component="section" aria-labelledby={id} gap="sm">
      <Title order={2} id={id}>
        {title}
      </Title>
      {children}
    </Stack>
  );
}

interface LoadedProps<T> {
  query: { isPending: boolean; isError: boolean; error: unknown; data: T | undefined };
  children: (data: T) => ReactNode;
}

/** Loading, a failure, or the content of a query-backed section. */
export function Loaded<T>({ query, children }: LoadedProps<T>) {
  if (query.isPending) return <LoadingSkeleton lines={2} />;
  if (query.isError || query.data === undefined) return <ErrorNotice error={query.error} />;
  return <>{children(query.data)}</>;
}
