import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { setSessionExpiredHandler } from "@/api/client";
import { useLogout, useMe } from "@/api/hooks/auth";
import type { Me } from "@/api/types";
import { clearDrafts, EXPIRED_PATH } from "./session";

export interface Session {
  /** Who is signed in, or null. */
  user: Me | null;
  /** True until `me` has answered. */
  loading: boolean;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession must be used inside SessionProvider");
  return session;
}

// Who is signed in (from `me`), signing out, and what happens when the session ends.
// In mock mode `me` is answered by the persona's contract, so the session just works.
export function SessionProvider({ children }: { children: ReactNode }) {
  const me = useMe();
  const logout = useLogout();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Ending a session, by signing out or by expiry: nothing of it stays in the browser.
  const endSession = useCallback(
    (to: string) => {
      queryClient.clear();
      clearDrafts();
      navigate(to, { replace: true });
    },
    [queryClient, navigate],
  );

  useEffect(() => {
    setSessionExpiredHandler(() => endSession(EXPIRED_PATH));
    return () => setSessionExpiredHandler(null);
  }, [endSession]);

  const { mutateAsync } = logout;
  const signOut = useCallback(async () => {
    try {
      await mutateAsync();
    } catch {
      // The server session may already be gone; sign out locally all the same.
    }
    endSession("/sign-in");
  }, [mutateAsync, endSession]);

  const user = me.data ?? null;
  const loading = !user && (me.isPending || me.isFetching);
  const session = useMemo(() => ({ user, loading, signOut }), [user, loading, signOut]);
  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
}
