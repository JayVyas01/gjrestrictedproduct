import { describe, expect, it } from "vitest";
import { apiGet } from "@/api/client";
import type { Me } from "@/api/types";
import { contract, contracts, createHandlers } from "@/test/handlers";
import { server } from "@/test/server";
import { mockHandlers, mockPersona, PERSONAS } from "./browser";

describe("mock mode personas", () => {
  it("every persona names captured contracts", () => {
    for (const names of Object.values(PERSONAS)) {
      for (const name of names) expect(Object.keys(contracts)).toContain(name);
    }
  });

  it("?as= picks the persona and keeps it for the tab; seller by default", () => {
    expect(mockPersona("")).toBe("seller");
    expect(mockPersona("?as=officer")).toBe("officer");
    expect(mockPersona("")).toBe("officer");
    expect(mockPersona("?as=nobody")).toBe("officer");
  });

  it("mock mode is a demo: the persona list and the inbox answer (tests default to 404)", async () => {
    await expect(apiGet("/api/demo/personas")).rejects.toMatchObject({ status: 404 });
    server.use(...mockHandlers(""));
    expect(await apiGet("/api/demo/personas")).toEqual(contract("demo_personas"));
    expect(await apiGet("/api/demo/inbox")).toEqual(contract("demo_inbox"));
  });

  it("the buyer-stock persona sees a sale over their stock limit", async () => {
    server.use(...createHandlers(PERSONAS["buyer-stock"]));
    expect(await apiGet("/api/transactions/TXZWSADK68UJ")).toEqual(
      contract("transaction_detail_buyer_stock_limit"),
    );
  });

  it("the officer persona is answered as the officer", async () => {
    server.use(...createHandlers(PERSONAS.officer));
    expect(await apiGet<Me>("/api/auth/me")).toEqual(contract("me_personnel"));
  });
});
