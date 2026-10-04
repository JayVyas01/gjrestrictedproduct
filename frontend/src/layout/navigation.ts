import type { Me } from "@/api/types";
import { holdsDistrictPosition } from "@/auth/session";
import { HEAD_PATHS, OWNER_PATHS, type OverviewPaths } from "@/features/overview/paths";
import type en from "@/i18n/en.json";

export interface NavItem {
  to: string;
  label: `nav.${keyof typeof en.nav}`;
  /** Matches only this exact path (a role's home), so it isn't "current" on every page. */
  end?: boolean;
}

/** The read-only lists of the Head Authority and the Software Owner. */
function overviewLists(paths: OverviewPaths): NavItem[] {
  return [
    { to: paths.transactions, label: "nav.transactions" },
    { to: paths.batches, label: "nav.batches" },
    { to: paths.reviewPeriods, label: "nav.reviewPeriods" },
    { to: paths.licences, label: "nav.licences" },
  ];
}

/** The navigation links for who is signed in (fixed paths only). */
export function navItems(user: Me): NavItem[] {
  switch (user.role) {
    case "LICENSEE":
      return [
        { to: "/licensee", label: "nav.home", end: true },
        { to: "/licensee/transactions", label: "nav.transactions" },
        { to: "/licensee/sale/new", label: "nav.newSale" },
      ];
    case "PERSONNEL":
      return [
        { to: "/personnel", label: "nav.home", end: true },
        { to: "/personnel/transactions", label: "nav.transactions" },
        ...(holdsDistrictPosition(user)
          ? [
              { to: "/personnel/batches", label: "nav.batches" } as const,
              { to: "/rule-changes", label: "nav.ruleChanges" } as const,
            ]
          : []),
      ];
    case "LICENSING_AUTHORITY":
      return [
        { to: "/authority", label: "nav.home", end: true },
        { to: "/authority/licences", label: "nav.licences" },
        { to: "/authority/licence-types", label: "nav.licenceTypes" },
        { to: "/authority/review-periods", label: "nav.reviewPeriods" },
        { to: "/rule-changes", label: "nav.ruleChanges" },
      ];
    case "HEAD_AUTHORITY":
      return [
        { to: HEAD_PATHS.home, label: "nav.home", end: true },
        { to: "/rule-changes", label: "nav.ruleChanges" },
        ...overviewLists(HEAD_PATHS),
      ];
    case "SOFTWARE_OWNER":
      return [
        { to: OWNER_PATHS.home, label: "nav.overview", end: true },
        ...overviewLists(OWNER_PATHS),
        { to: "/rule-changes", label: "nav.ruleChanges" },
      ];
  }
}
