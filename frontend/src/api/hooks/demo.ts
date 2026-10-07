import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  completeDemoSignup,
  listDemoInbox,
  listDemoPersonas,
  listDemoSignupCandidates,
  startDemoSignup,
} from "../demo";
import type { DemoSignupForm } from "../types";
import { isBackground, keys } from "./keys";

/** The demo SMS inbox refreshes this often while it is open. */
export const INBOX_POLL_MS = 3_000;

/**
 * Whether this is a demo, and its personas: asked once and kept for the page's life. Any
 * failure (a 404 outside demo mode) means "not a demo", without a retry or an error shown.
 */
export function useDemoPersonas() {
  return useQuery({
    queryKey: keys.demoPersonas,
    queryFn: listDemoPersonas,
    retry: false,
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

/** The inbox, polled every 3 seconds while a component using it is mounted (the open drawer). */
export function useDemoInbox() {
  return useQuery({
    queryKey: keys.demoInbox,
    queryFn: (context) => listDemoInbox({ background: isBackground(context) }),
    refetchInterval: INBOX_POLL_MS,
  });
}

/** Licensed businesses not yet signed up ("Pick a demo business"). */
export function useDemoSignupCandidates(enabled = true) {
  return useQuery({
    queryKey: keys.demoSignupCandidates,
    queryFn: listDemoSignupCandidates,
    enabled,
  });
}

export function useStartDemoSignup() {
  return useMutation({
    mutationFn: (form: DemoSignupForm) => startDemoSignup(form),
  });
}

/** The account now exists: the business leaves the candidates, and the personas may change. */
export function useCompleteDemoSignup() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ challengeId, code }: { challengeId: string; code: string }) =>
      completeDemoSignup(challengeId, code),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.demoSignupCandidates }),
  });
}
