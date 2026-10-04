import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getMe, logout, startLogin, verifyLogin } from "../auth";
import { keys } from "./keys";

export function useMe(enabled = true) {
  return useQuery({ queryKey: keys.me, queryFn: getMe, enabled, retry: false });
}

export function useStartLogin() {
  return useMutation({
    mutationFn: ({ userId, password }: { userId: string; password: string }) =>
      startLogin(userId, password),
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

export function useLogout() {
  const client = useQueryClient();
  return useMutation({ mutationFn: logout, onSettled: () => client.clear() });
}
