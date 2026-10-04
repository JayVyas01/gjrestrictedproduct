// Mock mode (`npm run dev:mock`): the MSW service worker answers /api with the same
// contract-backed handlers as the tests, so the screens can be reviewed without a backend.
// main.tsx imports this file only when import.meta.env.DEV and VITE_MOCK_API === "1",
// so it never reaches a production build.

import { setupWorker } from "msw/browser";
import { createHandlers } from "@/test/handlers";

/** `?as=` → the contracts that make the mock API answer as that person. */
export const PERSONAS: Record<string, string[]> = {
  seller: ["me_licensee", "home_licensee", "transaction_detail_seller"],
  buyer: ["me_licensee", "home_licensee", "transaction_detail_buyer"],
  "buyer-stock": ["me_licensee", "home_licensee", "transaction_detail_buyer_stock_limit"],
  officer: ["me_personnel", "home_personnel", "transaction_detail_officer"],
  superintendent: [
    "me_superintendent",
    "home_superintendent",
    "transaction_detail_superintendent_final",
  ],
  la: ["me_licensing_authority", "home_licensing_authority", "transaction_detail_authority"],
  head: ["me_head_authority", "home_head_authority", "transaction_detail_authority"],
};

const PERSONA_KEY = "gj.mock.as";

/** The persona from `?as=` (remembered for the tab, so navigation keeps it); seller by default. */
export function mockPersona(search = window.location.search): string {
  const asked = new URLSearchParams(search).get("as");
  if (asked && asked in PERSONAS) sessionStorage.setItem(PERSONA_KEY, asked);
  const kept = sessionStorage.getItem(PERSONA_KEY);
  return kept && kept in PERSONAS ? kept : "seller";
}

export async function startMockWorker(): Promise<void> {
  const worker = setupWorker(...createHandlers(PERSONAS[mockPersona()]));
  await worker.start({ onUnhandledRequest: "bypass", quiet: true });
}
