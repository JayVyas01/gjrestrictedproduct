import type { ReactElement } from "react";
import { Navigate, Outlet, type RouteObject } from "react-router-dom";
import type { Role } from "@/api/types";
import { LandingRedirect, RequireRole } from "@/auth/RequireRole";
import { SessionProvider } from "@/auth/SessionProvider";
import { SignInPage } from "@/auth/SignInPage";
import { AuthorityHomePage } from "@/features/authority/AuthorityHomePage";
import { LicencePage } from "@/features/authority/LicencePage";
import { LicencesPage } from "@/features/authority/LicencesPage";
import { LicenceTypesPage } from "@/features/authority/LicenceTypesPage";
import { ReviewPeriodsPage } from "@/features/authority/ReviewPeriodsPage";
import { BatchesPage } from "@/features/batches/BatchesPage";
import { BatchPage } from "@/features/batches/BatchPage";
import { LicenseeHomePage } from "@/features/licensee/LicenseeHomePage";
import { LicenseeTransactionsPage } from "@/features/licensee/LicenseeTransactionsPage";
import { TRANSACTIONS_PATH } from "@/features/licensee/paths";
import { BATCHES_PATH, PERSONNEL_TRANSACTIONS_PATH } from "@/features/personnel/paths";
import { PersonnelHomePage } from "@/features/personnel/PersonnelHomePage";
import { PersonnelTransactionsPage } from "@/features/personnel/PersonnelTransactionsPage";
import { NewRuleChangePage } from "@/features/governance/NewRuleChangePage";
import { RuleChangePage } from "@/features/governance/RuleChangePage";
import { RuleChangesPage } from "@/features/governance/RuleChangesPage";
import { OverviewHomePage } from "@/features/overview/OverviewHomePage";
import { OverviewTransactionsPage } from "@/features/overview/OverviewTransactionsPage";
import { HEAD_PATHS, OWNER_PATHS, type OverviewPaths } from "@/features/overview/paths";
import { NewSalePage } from "@/features/sale/NewSalePage";
import { TransactionPage } from "@/features/transactions/TransactionPage";
import { AppShell } from "@/layout/AppShell";

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
