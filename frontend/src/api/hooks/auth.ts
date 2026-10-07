import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { changePassword, getMe, logout, startLogin, verifyLogin, type LoginStart } from "../auth";
import type { PasswordChange } from "../types";
import { keys } from "./keys";

export function useMe(enabled = true) {
  return useQuery({ queryKey: keys.me, queryFn: getMe, enabled, retry: false });
}

export function useStartLogin() {
  return useMutation({
    mutationFn: (body: LoginStart) => startLogin(body),
  });
}

export function useVerifyLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ challengeId, code }: { challengeId: string; code: string }) =>
      verifyLogin(challengeId, code),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.me }),
  });
}

/**
 * Choose a new password. Afterwards `me` is fetched again (before this resolves, so the guards
 * see the flag cleared) and, in a demo, the personas (the picker shows the new password).
 */
export function useChangePassword() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: PasswordChange) => changePassword(body),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.me }),
        client.invalidateQueries({ queryKey: keys.demoPersonas }),
      ]),
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({ mutationFn: logout, onSettled: () => client.clear() });
}
