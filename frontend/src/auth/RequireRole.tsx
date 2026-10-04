import { Center, Loader } from "@mantine/core";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, Outlet } from "react-router-dom";
import type { Role } from "@/api/types";
import { landingFor } from "./session";
import { useSession } from "./SessionProvider";

// Guards a route: signed-out visitors go to sign-in, the wrong role goes to its own home.
// Without `roles`, any signed-in user may pass.
export function RequireRole({ roles, children }: { roles?: Role[]; children?: ReactNode }) {
  const { t } = useTranslation();
  const { user, loading } = useSession();
  if (loading) {
    return (
      <Center mih="50vh">
        <Loader role="status" aria-label={t("common.loading")} />
      </Center>
    );
  }
  if (!user) return <Navigate to="/sign-in" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to={landingFor(user.role)} replace />;
  return children ?? <Outlet />;
}

/** `/`: each role's home. */
export function LandingRedirect() {
  const { user } = useSession();
  return <Navigate to={user ? landingFor(user.role) : "/sign-in"} replace />;
}
