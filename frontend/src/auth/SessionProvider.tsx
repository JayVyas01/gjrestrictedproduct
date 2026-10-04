import { Button, Group, Modal, Stack, Text } from "@mantine/core";
import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { ApiError, lastActiveRequestAt, setSessionExpiredHandler } from "@/api/client";
import { useLogout, useMe } from "@/api/hooks/auth";
import { keys } from "@/api/hooks/keys";
import type { Me } from "@/api/types";
import { clearDrafts, EXPIRED_PATH, hasDrafts } from "./session";

/** No input for this long: the "you'll be signed out" warning. */
export const IDLE_WARNING_MS = 14 * 60_000;
/** No input for this long: signed out (the server's SESSION_COOKIE_AGE is the same 15 minutes). */
export const IDLE_SIGN_OUT_MS = 15 * 60_000;
/**
 * Input while no request has reached the server for this long sends one (`me`), so someone
 * typing a long form is not timed out by the server. The 30-second polls don't count: they are
 * background refreshes, which the server does not treat as activity.
 */
export const KEEP_ALIVE_MS = 5 * 60_000;

/** What counts as the user doing something. Listened for on window, in the capture phase. */
const ACTIVITY_EVENTS = ["pointerdown", "pointermove", "keydown", "touchstart", "wheel", "scroll"];

function isSignedOutError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 403;
}

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

interface IdleProps {
  /** Input after a quiet spell: an ordinary request, which extends the server session. */
  keepAlive: () => void;
  /** 15 minutes without input. */
  onExpire: () => void;
}

// The idle timeout: user input (pointer, key, touch, scroll) starts the 14 minutes again; then
// a warning, and a minute later sign-out. While the warning shows, only "Stay signed in" (or
// closing it) counts, so a stray mouse movement can't dismiss it unseen.
function IdleTimeout({ keepAlive, onExpire }: IdleProps) {
  const { t } = useTranslation();
  const [warning, setWarning] = useState(false);
  const warningShown = useRef(false);
  const restart = useRef<() => void>(() => {});
  const lastKeepAlive = useRef(0);
  const actions = useRef({ keepAlive, onExpire });
  useEffect(() => {
    actions.current = { keepAlive, onExpire };
  }, [keepAlive, onExpire]);

  useEffect(() => {
    let warnTimer = 0;
    let expireTimer = 0;
    const start = () => {
      window.clearTimeout(warnTimer);
      window.clearTimeout(expireTimer);
      warnTimer = window.setTimeout(() => {
        warningShown.current = true;
        setWarning(true);
      }, IDLE_WARNING_MS);
      expireTimer = window.setTimeout(() => actions.current.onExpire(), IDLE_SIGN_OUT_MS);
    };
    const activity = () => {
      if (warningShown.current) return;
      start();
      const now = Date.now();
      const lastRequest = Math.max(lastActiveRequestAt(), lastKeepAlive.current);
      if (now - lastRequest > KEEP_ALIVE_MS) {
        lastKeepAlive.current = now;
        actions.current.keepAlive();
      }
    };
    restart.current = start;
    start();
    const options = { capture: true, passive: true };
    ACTIVITY_EVENTS.forEach((name) => window.addEventListener(name, activity, options));
    return () => {
      window.clearTimeout(warnTimer);
      window.clearTimeout(expireTimer);
      ACTIVITY_EVENTS.forEach((name) => window.removeEventListener(name, activity, options));
    };
  }, []);

  const stay = () => {
    warningShown.current = false;
    setWarning(false);
    restart.current();
    lastKeepAlive.current = Date.now();
    actions.current.keepAlive();
  };

  return (
    <Modal
      opened={warning}
      onClose={stay}
      title={t("session.idleTitle")}
      centered
      closeButtonProps={{ "aria-label": t("common.close") }}
    >
      <Stack>
        <Text>{t("session.idleBody")}</Text>
        <Group justify="flex-end">
          <Button onClick={stay} data-autofocus>
            {t("session.staySignedIn")}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

// Who is signed in (from `me`), signing out, and what happens when the session ends: by
// signing out, by the server (a 403 that `me` confirms), by 15 minutes without input, or
// before this page loaded (left-over drafts or data). In mock mode `me` is answered by the
// persona's contract, so the session just works.
export function SessionProvider({ children }: { children: ReactNode }) {
  const me = useMe();
  const logout = useLogout();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Ending a session, by signing out or by expiry: nothing of it stays in the browser.
  // The cache is cleared again once the page being left has gone, since its queries can
  // fetch again while it re-renders on the way out.
  const [ended, setEnded] = useState(0);
  const endSession = useCallback(
    (to: string) => {
      queryClient.clear();
      clearDrafts();
      navigate(to, { replace: true });
      setEnded((count) => count + 1);
    },
    [queryClient, navigate],
  );
  useEffect(() => {
    if (ended) queryClient.clear();
  }, [ended, queryClient]);

  useEffect(() => {
    setSessionExpiredHandler(() => endSession(EXPIRED_PATH));
    return () => setSessionExpiredHandler(null);
  }, [endSession]);

  // `me` says nobody is signed in (403). Anything a session left behind (a draft, cached data)
  // is removed, and if there was any, the session must have ended: say so on the sign-in page.
  // Another failure (offline, 5xx) says nothing about the session and changes nothing.
  const signedOut = me.isError && isSignedOutError(me.error);
  useEffect(
    () =>
      queryClient.getQueryCache().subscribe((event) => {
        if (event.type !== "updated" || event.action.type !== "error") return;
        const key = event.query.queryKey as readonly unknown[];
        if (key[0] !== keys.me[0] || !isSignedOutError(event.action.error)) return;
        const leftOver =
          hasDrafts() ||
          queryClient
            .getQueryCache()
            .getAll()
            .some((query) => query.queryKey[0] !== keys.me[0] && query.state.data !== undefined);
        if (leftOver) endSession(EXPIRED_PATH);
      }),
    [queryClient, endSession],
  );

  const { mutateAsync } = logout;
  const endOnServer = useCallback(
    async (to: string) => {
      try {
        await mutateAsync();
      } catch {
        // The server session may already be gone; sign out locally all the same.
      }
      endSession(to);
    },
    [mutateAsync, endSession],
  );
  const signOut = useCallback(() => endOnServer("/sign-in"), [endOnServer]);
  const expire = useCallback(() => void endOnServer(EXPIRED_PATH), [endOnServer]);
  const { refetch } = me;
  const keepAlive = useCallback(() => void refetch(), [refetch]);

  // A failed refetch keeps the last data, so a 403 from `me` must override what is cached.
  const user = signedOut ? null : (me.data ?? null);
  const loading = !user && !signedOut && (me.isPending || me.isFetching);
  const session = useMemo(() => ({ user, loading, signOut }), [user, loading, signOut]);
  return (
    <SessionContext.Provider value={session}>
      {children}
      {user && <IdleTimeout keepAlive={keepAlive} onExpire={expire} />}
    </SessionContext.Provider>
  );
}
