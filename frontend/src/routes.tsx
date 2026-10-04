import type { ReactElement } from "react";
import { Navigate, Outlet, type RouteObject } from "react-router-dom";
import type { Role } from "@/api/types";
import { LandingRedirect, RequireRole } from "@/auth/RequireRole";
import { SessionProvider } from "@/auth/SessionProvider";
import { SignInPage } from "@/auth/SignInPage";
import { TRANSACTIONS_PATH } from "@/features/licensee/paths";
import { BATCHES_PATH, PERSONNEL_TRANSACTIONS_PATH } from "@/features/personnel/paths";
import { HEAD_PATHS, OWNER_PATHS, type OverviewPaths } from "@/features/overview/paths";
import { AppShell } from "@/layout/AppShell";
import { lazyPage } from "@/lazyPage";

// Each page's code loads on first visit, in a chunk per feature area (vite.config.ts), so the
// first download carries only the shell and sign-in.
const AuthorityHomePage = lazyPage(() =>
  import("@/features/authority/AuthorityHomePage").then((m) => m.AuthorityHomePage),
);
const LicencePage = lazyPage(() =>
  import("@/features/authority/LicencePage").then((m) => m.LicencePage),
);
const LicencesPage = lazyPage(() =>
  import("@/features/authority/LicencesPage").then((m) => m.LicencesPage),
);
const LicenceTypesPage = lazyPage(() =>
  import("@/features/authority/LicenceTypesPage").then((m) => m.LicenceTypesPage),
);
const ReviewPeriodsPage = lazyPage(() =>
  import("@/features/authority/ReviewPeriodsPage").then((m) => m.ReviewPeriodsPage),
);
const BatchesPage = lazyPage(() =>
  import("@/features/batches/BatchesPage").then((m) => m.BatchesPage),
);
const BatchPage = lazyPage(() => import("@/features/batches/BatchPage").then((m) => m.BatchPage));
const LicenseeHomePage = lazyPage(() =>
  import("@/features/licensee/LicenseeHomePage").then((m) => m.LicenseeHomePage),
);
const LicenseeTransactionsPage = lazyPage(() =>
  import("@/features/licensee/LicenseeTransactionsPage").then((m) => m.LicenseeTransactionsPage),
);
const PersonnelHomePage = lazyPage(() =>
  import("@/features/personnel/PersonnelHomePage").then((m) => m.PersonnelHomePage),
);
const PersonnelTransactionsPage = lazyPage(() =>
  import("@/features/personnel/PersonnelTransactionsPage").then((m) => m.PersonnelTransactionsPage),
);
const NewRuleChangePage = lazyPage(() =>
  import("@/features/governance/NewRuleChangePage").then((m) => m.NewRuleChangePage),
);
const RuleChangePage = lazyPage(() =>
  import("@/features/governance/RuleChangePage").then((m) => m.RuleChangePage),
);
const RuleChangesPage = lazyPage(() =>
  import("@/features/governance/RuleChangesPage").then((m) => m.RuleChangesPage),
);
const OverviewHomePage = lazyPage(() =>
  import("@/features/overview/OverviewHomePage").then((m) => m.OverviewHomePage),
);
const OverviewTransactionsPage = lazyPage(() =>
  import("@/features/overview/OverviewTransactionsPage").then((m) => m.OverviewTransactionsPage),
);
const NewSalePage = lazyPage(() =>
  import("@/features/sale/NewSalePage").then((m) => m.NewSalePage),
);
const TransactionPage = lazyPage(() =>
  import("@/features/transactions/TransactionPage").then((m) => m.TransactionPage),
);

function SessionRoot() {
  return (
    <SessionProvider>
      <Outlet />
    </SessionProvider>
  );
}

function screen(path: string, roles: Role[], element: ReactElement): RouteObject {
  return { path, element: <RequireRole roles={roles}>{element}</RequireRole> };
}

/**
 * The Head Authority's or the Software Owner's read-only screens under their base path: the
 * shared lists and details, with every action hidden (`readOnly`) or never offered by the server
 * (`can_decide` and `can_sign` are false for these roles).
 */
function overviewScreens(paths: OverviewPaths, roles: Role[]): RouteObject[] {
  const at = (path: string) => path.slice(1);
  return [
    screen(at(paths.home), roles, <OverviewHomePage paths={paths} />),
    screen(at(paths.transactions), roles, <OverviewTransactionsPage basePath={paths.transactions} />),
    screen(
      `${at(paths.transactions)}/:reference`,
      roles,
      <TransactionPage listPath={paths.transactions} />,
    ),
    screen(at(paths.batches), roles, <BatchesPage basePath={paths.batches} />),
    screen(`${at(paths.batches)}/:id`, roles, <BatchPage listPath={paths.batches} readOnly />),
    screen(at(paths.reviewPeriods), roles, <ReviewPeriodsPage readOnly />),
    screen(at(paths.licences), roles, <LicencesPage basePath={paths.licences} />),
    screen(`${at(paths.licences)}/:id`, roles, <LicencePage listPath={paths.licences} />),
  ];
}

const L: Role[] = ["LICENSEE"];
const P: Role[] = ["PERSONNEL"];
const LA: Role[] = ["LICENSING_AUTHORITY"];
/** Drafters (the page itself checks personnel hold a district position). */
const DRAFTERS: Role[] = ["LICENSING_AUTHORITY", "PERSONNEL", "HEAD_AUTHORITY"];
/** Drafters, and the Software Owner read-only. */
const RULE_CHANGES: Role[] = [...DRAFTERS, "SOFTWARE_OWNER"];

// The app's routes: sign-in, then the shell with each role's screens behind RequireRole.
export const routes: RouteObject[] = [
  {
    element: <SessionRoot />,
    children: [
      { path: "/sign-in", element: <SignInPage /> },
      {
        path: "/",
        element: (
          <RequireRole>
            <AppShell />
          </RequireRole>
        ),
        children: [
          { index: true, element: <LandingRedirect /> },
          screen("licensee", L, <LicenseeHomePage />),
          screen("licensee/transactions", L, <LicenseeTransactionsPage />),
          screen(
            "licensee/transactions/:reference",
            L,
            <TransactionPage listPath={TRANSACTIONS_PATH} />,
          ),
          screen("licensee/sale/new", L, <NewSalePage />),
          screen("personnel", P, <PersonnelHomePage />),
          screen("personnel/transactions", P, <PersonnelTransactionsPage />),
          screen(
            "personnel/transactions/:reference",
            P,
            <TransactionPage listPath={PERSONNEL_TRANSACTIONS_PATH} />,
          ),
          screen("personnel/batches", P, <BatchesPage />),
          screen("personnel/batches/:id", P, <BatchPage listPath={BATCHES_PATH} />),
          screen("authority", LA, <AuthorityHomePage />),
          screen("authority/licences", LA, <LicencesPage />),
          screen("authority/licences/:id", LA, <LicencePage />),
          screen("authority/licence-types", LA, <LicenceTypesPage />),
          screen("authority/review-periods", LA, <ReviewPeriodsPage />),
          ...overviewScreens(HEAD_PATHS, ["HEAD_AUTHORITY"]),
          ...overviewScreens(OWNER_PATHS, ["SOFTWARE_OWNER"]),
          screen("rule-changes", RULE_CHANGES, <RuleChangesPage />),
          screen("rule-changes/new", DRAFTERS, <NewRuleChangePage />),
          screen("rule-changes/:id", RULE_CHANGES, <RuleChangePage />),
        ],
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
];
