import {
  createTheme,
  type CSSVariablesResolver,
  type MantineColorsTuple,
} from "@mantine/core";

// Design W2, "Navy official". This file is the only place colours are defined.

export const NAVY = "#1B365D";
export const PAGE_BACKGROUND = "#F5F7FA";
export const SAFFRON = "#E8A33D";

// Lightest to darkest; index 6 is the brand navy (the primary shade).
const navy: MantineColorsTuple = [
  "#E9EEF5",
  "#CFD9E7",
  "#A9BBD3",
  "#7F99BC",
  "#5878A3",
  "#3A5A87",
  NAVY,
  "#162D4E",
  "#11233E",
  "#0B182B",
];

// Saffron marks attention only: the bell count, the "What's next" accent and "Awaiting you".
// Index 5 is the brand saffron. It is light, so text on it must be dark (autoContrast does this).
const saffron: MantineColorsTuple = [
  "#FDF5E8",
  "#FAE6C4",
  "#F5D29A",
  "#F0BD6E",
  "#ECAE52",
  SAFFRON,
  "#D08F2C",
  "#B07824",
  "#8F611C",
  "#6E4A14",
];

export type StatusTone = "approved" | "rejected" | "cancelled" | "waiting";

// A green dark enough for white text (5.4:1); Mantine's darkest green, #2b8a3e, is only 4.4:1.
const APPROVED_GREEN = "#1F7A35";

// Colours for each status tone (used by StatusBadge as filled badges). White text on the green,
// red.9 (#c92a2a, 5.5:1) and gray.7 (8.2:1) meets WCAG AA; saffron gets dark text (9.7:1).
export const STATUS_COLORS: Record<StatusTone, string> = {
  approved: APPROVED_GREEN,
  rejected: "red.9",
  cancelled: "gray.7",
  waiting: "saffron.5",
};

/** "Awaiting you" (attention, saffron). */
export const AWAITING_YOU_COLOR = "saffron.5";
/** Allowance ticks and crosses, and a warning banner. */
export const ALLOWED_COLOR = APPROVED_GREEN;
export const NOT_ALLOWED_COLOR = "red.9";
/** The saffron left accent of the What's next card. */
export const ACCENT_BORDER = `4px solid ${SAFFRON}`;

export const theme = createTheme({
  primaryColor: "navy",
  primaryShade: 6,
  colors: { navy, saffron },
  // Picks black or white text by background luminance, so filled saffron badges stay readable (WCAG AA).
  autoContrast: true,
  defaultRadius: "sm",
  fontFamily:
    'system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", "Helvetica Neue", Arial, sans-serif',
  headings: {
    fontFamily:
      'system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", "Helvetica Neue", Arial, sans-serif',
  },
});

// Page background light grey-blue; cards stay white.
export const cssVariablesResolver: CSSVariablesResolver = () => ({
  variables: {},
  light: { "--mantine-color-body": PAGE_BACKGROUND },
  dark: {},
});
