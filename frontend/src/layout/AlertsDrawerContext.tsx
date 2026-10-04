import { useDisclosure } from "@mantine/hooks";
import { createContext, useContext, useMemo, type ReactNode } from "react";
import { AlertsDrawer } from "./AlertsDrawer";

interface AlertsDrawerControls {
  /** Opens the alerts drawer (a no-op for a role without one). */
  open: () => void;
}

const AlertsDrawerContext = createContext<AlertsDrawerControls>({ open: () => {} });

interface Props {
  /** The signed-in role has the bell and the drawer (personnel and the Head Authority). */
  enabled: boolean;
  children: ReactNode;
}

// One alerts drawer for the shell, opened from the bell or from a page (the personnel home's
// alerts section).
export function AlertsDrawerProvider({ enabled, children }: Props) {
  const [opened, { open, close }] = useDisclosure(false);
  const controls = useMemo(() => ({ open }), [open]);
  return (
    <AlertsDrawerContext.Provider value={controls}>
      {children}
      {enabled && <AlertsDrawer opened={opened} onClose={close} />}
    </AlertsDrawerContext.Provider>
  );
}

export function useAlertsDrawer(): AlertsDrawerControls {
  return useContext(AlertsDrawerContext);
}
