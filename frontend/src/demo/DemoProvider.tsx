import { useDisclosure } from "@mantine/hooks";
import { useCallback, useMemo, useRef, type ReactNode } from "react";
import { useDemoPersonas } from "@/api/hooks/demo";
import { SmsInbox } from "./SmsInbox";
import { DemoContext, type CodeFill, type Demo } from "./useDemo";

// Demo mode is a runtime mode: production builds carry this code, but it stays dormant unless
// the server answers the persona list (it answers 404 outside demo mode). In a demo it supplies
// the personas and one SMS inbox drawer, reachable from sign-in and the signed-in header.
export function DemoProvider({ children }: { children: ReactNode }) {
  const personas = useDemoPersonas();
  const enabled = personas.isSuccess;
  const [inboxOpen, { open, close }] = useDisclosure(false);
  const fill = useRef<CodeFill | null>(null);

  const registerCodeFill = useCallback((next: CodeFill) => {
    fill.current = next;
    return () => {
      if (fill.current === next) fill.current = null;
    };
  }, []);

  const demo = useMemo<Demo>(
    () => ({
      enabled,
      personas: personas.data ?? [],
      inboxOpen: enabled && inboxOpen,
      openInbox: open,
      registerCodeFill,
    }),
    [enabled, personas.data, inboxOpen, open, registerCodeFill],
  );

  return (
    <DemoContext.Provider value={demo}>
      {children}
      {enabled && <SmsInbox opened={inboxOpen} onClose={close} codeFill={() => fill.current} />}
    </DemoContext.Provider>
  );
}
