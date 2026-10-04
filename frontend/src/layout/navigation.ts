import type { Me } from "@/api/types";
import { holdsDistrictPosition } from "@/auth/session";
import type en from "@/i18n/en.json";

export interface NavItem {
  to: string;
  label: `nav.${keyof typeof en.nav}`;
  /** Matches only this exact path (a role's home), so it isn't "current" on every page. */
  end?: boolean;
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
        { to: "/head", label: "nav.home", end: true },
        { to: "/rule-changes", label: "nav.ruleChanges" },
      ];
    case "SOFTWARE_OWNER":
      return [{ to: "/overview", label: "nav.overview", end: true }];
  }
}
