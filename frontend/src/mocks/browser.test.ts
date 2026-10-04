import { describe, expect, it } from "vitest";
import { apiGet } from "@/api/client";
import type { Me } from "@/api/types";
import { contract, contracts, createHandlers } from "@/test/handlers";
import { server } from "@/test/server";
import { mockPersona, PERSONAS } from "./browser";

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

  it("the officer persona is answered as the officer", async () => {
    server.use(...createHandlers(PERSONAS.officer));
    expect(await apiGet<Me>("/api/auth/me")).toEqual(contract("me_personnel"));
  });
});
