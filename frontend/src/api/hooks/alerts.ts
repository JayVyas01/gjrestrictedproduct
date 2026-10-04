import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { acknowledgeAlert, listAlerts } from "../alerts";
import { invalidate, keys, POLL_MS } from "./keys";

export function useAlerts(enabled = true) {
  return useQuery({
    queryKey: keys.alerts,
    queryFn: listAlerts,
    refetchInterval: POLL_MS,
    enabled,
  });
}

export function useAcknowledgeAlert() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) => acknowledgeAlert(id, note),
    onSuccess: () => invalidate(client, keys.alerts),
  });
}
