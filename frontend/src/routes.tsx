import type { ReactElement } from "react";
import { Navigate, Outlet, type RouteObject } from "react-router-dom";
import type { Role } from "@/api/types";
import { LandingRedirect, RequireRole } from "@/auth/RequireRole";
import { SessionProvider } from "@/auth/SessionProvider";
import { SignInPage } from "@/auth/SignInPage";
import { LicenseeHomePage } from "@/features/licensee/LicenseeHomePage";
import { LicenseeTransactionsPage } from "@/features/licensee/LicenseeTransactionsPage";
import { TRANSACTIONS_PATH } from "@/features/licensee/paths";
import { PERSONNEL_TRANSACTIONS_PATH } from "@/features/personnel/paths";
import { PersonnelHomePage } from "@/features/personnel/PersonnelHomePage";
import { PersonnelTransactionsPage } from "@/features/personnel/PersonnelTransactionsPage";
import { NewSalePage } from "@/features/sale/NewSalePage";
import { TransactionPage } from "@/features/transactions/TransactionPage";
import { AppShell } from "@/layout/AppShell";
import { PlaceholderPage, type PageKey } from "@/layout/PlaceholderPage";

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

function page(path: string, roles: Role[], title: PageKey): RouteObject {
  return screen(path, roles, <PlaceholderPage title={title} />);
}

const L: Role[] = ["LICENSEE"];
const P: Role[] = ["PERSONNEL"];
const LA: Role[] = ["LICENSING_AUTHORITY"];
const RULE_CHANGES: Role[] = ["LICENSING_AUTHORITY", "PERSONNEL", "HEAD_AUTHORITY"];

// The app's routes: sign-in, then the shell with each role's screens behind RequireRole.
// Placeholders stand in for the screens later tasks build.
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
          page("personnel/batches", P, "batches"),
          page("personnel/batches/:id", P, "batchDetail"),
          page("authority", LA, "authorityHome"),
          page("authority/licences", LA, "licences"),
          page("authority/licences/:id", LA, "licenceDetail"),
          page("authority/licence-types", LA, "licenceTypes"),
          page("authority/review-periods", LA, "reviewPeriods"),
          page("head", ["HEAD_AUTHORITY"], "headHome"),
          page("overview", ["SOFTWARE_OWNER"], "overview"),
          page("rule-changes", RULE_CHANGES, "ruleChanges"),
          page("rule-changes/new", RULE_CHANGES, "newRuleChange"),
          page("rule-changes/:id", RULE_CHANGES, "ruleChangeDetail"),
        ],
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
];
