import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  flagItem,
  getBatch,
  listBatches,
  listReviewSettings,
  requestSignOffCode,
  saveReviewSetting,
  signOff,
  type Flag,
  type ReviewPeriod,
} from "../oversight";
import type { BatchDetail } from "../types";
import { invalidate, keys } from "./keys";

export function useBatches() {
  return useQuery({ queryKey: keys.batches, queryFn: listBatches });
}

export function useBatch(id: number, enabled = true) {
  return useQuery({ queryKey: keys.batch(id), queryFn: () => getBatch(id), enabled });
}

function useBatchChange<A>(id: number, change: (args: A) => Promise<BatchDetail>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: change,
    onSuccess: (batch) => {
      client.setQueryData(keys.batch(id), batch);
      // A flag reaches the officer as an alert.
      return invalidate(client, keys.batches, keys.alerts);
    },
  });
}

export function useFlagItem(id: number) {
  return useBatchChange(id, (flag: Flag) => flagItem(id, flag));
}

export function useRequestSignOffCode() {
  return useMutation({ mutationFn: requestSignOffCode });
}

export function useSignOff(id: number) {
  return useBatchChange(id, ({ challengeId, code }: { challengeId: string; code: string }) =>
    signOff(id, challengeId, code),
  );
}

export function useReviewSettings() {
  return useQuery({ queryKey: keys.reviewSettings, queryFn: listReviewSettings });
}

export function useSaveReviewSetting() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ positionId, period }: { positionId: number; period: ReviewPeriod }) =>
      saveReviewSetting(positionId, period),
    onSuccess: () => invalidate(client, keys.reviewSettings),
  });
}
