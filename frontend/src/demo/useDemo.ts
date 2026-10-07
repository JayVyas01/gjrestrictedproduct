import { createContext, useContext, useEffect, useRef } from "react";
import type { DemoPersona } from "@/api/types";

/** Puts a code into the code input on screen. */
export type CodeFill = (code: string) => void;

export interface Demo {
  /** True only when the server answered the persona list (demo mode). */
  enabled: boolean;
  /** True while the persona list has not answered yet (demo mode not known). */
  loading: boolean;
  personas: DemoPersona[];
  inboxOpen: boolean;
  openInbox: () => void;
  /** The code input on screen offers itself to the inbox's "Use this code"; returns the undo. */
  registerCodeFill: (fill: CodeFill) => () => void;
}

/** Outside a DemoProvider (and outside demo mode) nothing demo-related shows or happens. */
export const NOT_A_DEMO: Demo = {
  enabled: false,
  loading: false,
  personas: [],
  inboxOpen: false,
  openInbox: () => {},
  registerCodeFill: () => () => {},
};

export const DemoContext = createContext<Demo>(NOT_A_DEMO);

/** Demo mode, its personas and the SMS inbox controls (see DemoProvider). */
export function useDemo(): Demo {
  return useContext(DemoContext);
}

/**
 * For a code input (sign-in's code step, the code dialog): while mounted, the inbox's
 * "Use this code" fills it through `fill` instead of copying the code. A no-op outside demo mode.
 */
export function useDemoCodeFill(fill: CodeFill): void {
  const { registerCodeFill } = useDemo();
  const latest = useRef(fill);
  useEffect(() => {
    latest.current = fill;
  });
  useEffect(() => registerCodeFill((code) => latest.current(code)), [registerCodeFill]);
}
