import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelTransaction,
  checkSale,
  decideTransaction,
  getTransaction,
  listTransactions,
  lookupBuyer,
  requestDecisionCode,
  startSale,
  type Decision,
  type TransactionFilters,
} from "../transactions";
import type { TransactionDetail } from "../types";
import { invalidate, keys } from "./keys";

export function useTransactions(filters: TransactionFilters = {}) {
  return useQuery({
    queryKey: keys.transactionList(filters),
    queryFn: () => listTransactions(filters),
  });
}

export function useTransaction(reference: string) {
  return useQuery({
    queryKey: keys.transaction(reference),
    queryFn: () => getTransaction(reference),
  });
}

export function useCheckSale() {
  return useMutation({ mutationFn: checkSale });
}

export function useLookupBuyer() {
  return useMutation({ mutationFn: lookupBuyer });
}

// Store the transaction the server returned, then refetch the lists, home counts and alerts.
function useTransactionChange<A>(change: (args: A) => Promise<TransactionDetail>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: change,
    onSuccess: (tx) => {
      client.setQueryData(keys.transaction(tx.reference), tx);
      return invalidate(client, keys.transactions, keys.alerts);
    },
  });
}

export function useStartSale() {
  return useTransactionChange(startSale);
}

export function useRequestDecisionCode() {
  return useMutation({ mutationFn: requestDecisionCode });
}

export function useDecideTransaction(reference: string) {
  return useTransactionChange((decision: Decision) => decideTransaction(reference, decision));
}

export function useCancelTransaction(reference: string) {
  return useTransactionChange(() => cancelTransaction(reference));
}
