import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  decideRuleChange,
  draftRuleChange,
  getRuleChange,
  listRuleChanges,
  requestRuleChangeCode,
  withdrawRuleChange,
  type RuleChangeDecision,
} from "../governance";
import type { ProposalStatus, RuleChange } from "../types";
import { invalidate, keys } from "./keys";

export function useRuleChanges(status: ProposalStatus | "" = "") {
  return useQuery({
    queryKey: keys.ruleChangeList(status),
    queryFn: () => listRuleChanges(status),
  });
}

export function useRuleChange(id: number) {
  return useQuery({ queryKey: keys.ruleChange(id), queryFn: () => getRuleChange(id) });
}

// An approved change alters the catalogue, so that is refetched too.
function useRuleChangeChange<A>(change: (args: A) => Promise<RuleChange>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: change,
    onSuccess: (proposal) => {
      client.setQueryData(keys.ruleChange(proposal.id), proposal);
      return invalidate(client, keys.ruleChanges, keys.catalogue);
    },
  });
}

export function useDraftRuleChange() {
  return useRuleChangeChange(draftRuleChange);
}

export function useWithdrawRuleChange(id: number) {
  return useRuleChangeChange(() => withdrawRuleChange(id));
}

export function useRequestRuleChangeCode() {
  return useMutation({ mutationFn: requestRuleChangeCode });
}

export function useDecideRuleChange(id: number) {
  return useRuleChangeChange((decision: RuleChangeDecision) => decideRuleChange(id, decision));
}
