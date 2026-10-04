import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { createQueryClient } from "@/App";
import { contract, serveContract } from "@/test/handlers";
import { server } from "@/test/server";
import type { TransactionDetail } from "../types";
import { useAlerts } from "./alerts";
import { useHome } from "./home";
import { keys, POLL_MS } from "./keys";
import { useDecideTransaction, useTransaction } from "./transactions";

function setup() {
  const client = createQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, wrapper };
}

function countRequests(path: string, body: unknown) {
  const calls = { count: 0 };
  server.use(
    http.get(path, () => {
      calls.count += 1;
      return HttpResponse.json(body as object);
    }),
  );
  return calls;
}

describe("query hooks", () => {
  it("useHome and useAlerts poll every 30 seconds", async () => {
    const { client, wrapper } = setup();
    renderHook(() => [useHome(), useAlerts()], { wrapper });
    await waitFor(() => expect(client.getQueryData(keys.alerts)).toBeDefined());
    for (const queryKey of [keys.home, keys.alerts]) {
      const [observer] = client.getQueryCache().find({ queryKey })!.observers;
      expect(observer!.options.refetchInterval).toBe(POLL_MS);
    }
  });

  it("serves a contract variant for one test", async () => {
    server.use(serveContract("transaction_detail_buyer_stock_limit"));
    const { wrapper } = setup();
    const { result } = renderHook(() => useTransaction("TX1"), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.allowed_outcomes).toEqual(["REJECT"]);
  });
});

describe("mutation hooks", () => {
  it("a decision stores the returned transaction and refetches home and the lists", async () => {
    const decided = contract<TransactionDetail>("transaction_detail_authority");
    const home = countRequests("/api/home", contract("home_licensee"));
    const lists = countRequests("/api/transactions", contract("transactions_list"));
    const { client, wrapper } = setup();
    const { result } = renderHook(
      () => ({ home: useHome(), decide: useDecideTransaction(decided.reference) }),
      { wrapper },
    );
    await waitFor(() => expect(home.count).toBe(1));
    client.setQueryData(keys.transactionList({}), []); // a cached list, now stale
    await result.current.decide.mutateAsync({
      challenge_id: "c",
      code: "123456",
      outcome: "APPROVE",
    });
    expect(client.getQueryData(keys.transaction(decided.reference))).toEqual(decided);
    expect(client.getQueryState(keys.transactionList({}))?.isInvalidated).toBe(true);
    expect(home.count).toBe(2);
    expect(lists.count).toBe(0); // no list is on screen, so it is only marked stale
  });
});
