// MSW handlers that serve the contracts captured from the real backend
// (backend/tests/test_api_contracts.py writes src/test/contracts/*.json). The unit tests and
// mock mode (src/mocks/browser.ts) both use them, so the mocks always match the real API.

import { http, HttpResponse, type HttpHandler } from "msw";

const files = import.meta.glob<unknown>("./contracts/*.json", { eager: true, import: "default" });

/** Every captured contract, by name (the file name without `.json`). */
export const contracts: Record<string, unknown> = Object.fromEntries(
  Object.entries(files).map(([path, body]) => [path.replace(/^.*\/|\.json$/g, ""), body]),
);

export function contract<T = unknown>(name: string): T {
  if (!(name in contracts)) throw new Error(`No contract named "${name}"`);
  // A fresh copy, so a test that changes it cannot affect another.
  return structuredClone(contracts[name]) as T;
}

type Method = "get" | "post" | "put";

interface Endpoint {
  method: Method;
  path: string;
  /** The contract served by default. */
  contract: string;
  status?: number;
  /** Other contracts captured from this endpoint (another role, another state). */
  variants?: string[];
}

// The CSRF view sets the cookie; the handler does the same so the client finds a token.
const CSRF_TOKEN = "mock-csrf-token";

// Order matters: MSW uses the first match, so fixed paths come before `:param` paths.
const ENDPOINTS: Endpoint[] = [
  { method: "post", path: "/api/auth/login", contract: "login_start" },
  { method: "post", path: "/api/auth/login/verify", contract: "login_verify" },
  {
    method: "get",
    path: "/api/auth/me",
    contract: "me_licensee",
    variants: [
      "me_personnel",
      "me_superintendent",
      "me_licensing_authority",
      "me_head_authority",
      "me_software_owner",
    ],
  },
  {
    method: "get",
    path: "/api/home",
    contract: "home_licensee",
    variants: [
      "home_personnel",
      "home_superintendent",
      "home_licensing_authority",
      "home_head_authority",
      "home_software_owner",
    ],
  },
  { method: "get", path: "/api/transactions", contract: "transactions_list" },
  { method: "post", path: "/api/transactions", contract: "transaction_created", status: 201 },
  {
    method: "post",
    path: "/api/transactions/check",
    contract: "transaction_check_ok",
    variants: ["transaction_check_refused"],
  },
  { method: "post", path: "/api/transactions/buyer-lookup", contract: "buyer_lookup" },
  {
    method: "get",
    path: "/api/transactions/:reference",
    contract: "transaction_detail_seller",
    variants: [
      "transaction_detail_buyer",
      "transaction_detail_buyer_stock_limit",
      "transaction_detail_officer",
      "transaction_detail_officer_two_step",
      "transaction_detail_superintendent_final",
      "transaction_detail_authority",
    ],
  },
  { method: "post", path: "/api/transactions/:reference/decision-code", contract: "decision_code" },
  {
    method: "post",
    path: "/api/transactions/:reference/decide",
    contract: "transaction_detail_authority",
  },
  {
    method: "post",
    path: "/api/transactions/:reference/cancel",
    contract: "transaction_detail_seller",
  },
  { method: "get", path: "/api/licences/mine", contract: "licences_mine" },
  { method: "post", path: "/api/licences/search", contract: "licence_search" },
  { method: "get", path: "/api/stock/mine", contract: "stock_mine" },
  { method: "get", path: "/api/catalogue/substances", contract: "catalogue_substances" },
  { method: "get", path: "/api/catalogue/classes", contract: "catalogue_classes" },
  { method: "get", path: "/api/catalogue/licence-types", contract: "catalogue_licence_types" },
  {
    method: "get",
    path: "/api/catalogue/approval-thresholds",
    contract: "catalogue_approval_thresholds",
  },
  { method: "get", path: "/api/alerts", contract: "alerts" },
  { method: "post", path: "/api/alerts/:id/acknowledge", contract: "alert_acknowledged" },
  { method: "get", path: "/api/oversight/batches", contract: "oversight_batches" },
  { method: "get", path: "/api/oversight/batches/:id", contract: "oversight_batch_detail" },
  { method: "post", path: "/api/oversight/batches/:id/flag", contract: "oversight_batch_detail" },
  { method: "post", path: "/api/oversight/batches/:id/sign-off-code", contract: "decision_code" },
  {
    method: "post",
    path: "/api/oversight/batches/:id/sign-off",
    contract: "oversight_batch_detail",
  },
  { method: "get", path: "/api/oversight/review-settings", contract: "review_settings" },
  { method: "put", path: "/api/oversight/review-settings/:id", contract: "review_setting_saved" },
  { method: "get", path: "/api/rule-changes", contract: "rule_changes" },
  {
    method: "post",
    path: "/api/rule-changes",
    contract: "rule_change_new_licence_type",
    status: 201,
  },
  {
    method: "get",
    path: "/api/rule-changes/:id",
    contract: "rule_change_rule_version",
    variants: ["rule_change_new_licence_type", "rule_change_threshold", "rule_change_decided"],
  },
  {
    method: "post",
    path: "/api/rule-changes/:id/withdraw",
    contract: "rule_change_new_licence_type",
  },
  { method: "post", path: "/api/rule-changes/:id/decision-code", contract: "decision_code" },
  { method: "post", path: "/api/rule-changes/:id/decide", contract: "rule_change_decided" },
  { method: "get", path: "/api/licences", contract: "licences_register" },
  { method: "get", path: "/api/licences/:id", contract: "licence_detail" },
];

// Demo mode only (D4). Outside it both answer 404, as the real server does, so by default the
// tests and mock mode run as a real deployment; `createHandlers(..., { demo: true })` (mock mode)
// or `server.use(...serveDemo())` (a test) turns the demo on.
const DEMO_ENDPOINTS: Endpoint[] = [
  { method: "get", path: "/api/demo/personas", contract: "demo_personas" },
  { method: "get", path: "/api/demo/inbox", contract: "demo_inbox" },
];

/** The demo endpoints, answering as in demo mode. */
export function serveDemo(): HttpHandler[] {
  return DEMO_ENDPOINTS.map((endpoint) => serve(endpoint.method, endpoint.path, endpoint.contract));
}

function notADemo(): HttpHandler[] {
  return DEMO_ENDPOINTS.map((endpoint) =>
    serve(endpoint.method, endpoint.path, "error_404_not_found", 404),
  );
}

function serve(method: Method, path: string, name: string, status = 200): HttpHandler {
  return http[method](path, () => HttpResponse.json(contract<object>(name), { status }));
}

function statusOf(name: string): number | undefined {
  const match = /^error_(\d{3})_/.exec(name);
  return match ? Number(match[1]) : undefined;
}

/**
 * The default handler for every endpoint the app uses. `selected` swaps in variants, e.g.
 * `createHandlers(["me_personnel", "home_personnel"])` for an officer.
 */
export function createHandlers(
  selected: string[] = [],
  { demo = false }: { demo?: boolean } = {},
): HttpHandler[] {
  const fixed: HttpHandler[] = [
    http.get("/api/auth/csrf", () => {
      document.cookie = `csrftoken=${CSRF_TOKEN}; path=/`;
      return new HttpResponse(null, { status: 204 });
    }),
    http.post("/api/auth/logout", () => new HttpResponse(null, { status: 204 })),
    http.get("/api/reason-codes", ({ request }) => {
      const kind = new URL(request.url).searchParams.get("kind") ?? "";
      const name = `reason_codes_${kind.toLowerCase()}`;
      if (!(name in contracts))
        return HttpResponse.json({ detail: "Unknown reason kind." }, { status: 400 });
      return HttpResponse.json(contract<object>(name));
    }),
  ];
  return [
    ...fixed,
    ...(demo ? serveDemo() : notADemo()),
    ...ENDPOINTS.map((endpoint) => {
      const chosen = selected.find((name) => endpoint.variants?.includes(name));
      return serve(endpoint.method, endpoint.path, chosen ?? endpoint.contract, endpoint.status);
    }),
  ];
}

export const handlers = createHandlers();

/**
 * One contract to serve instead of the default, for `server.use(...)` in a test:
 *   server.use(serveContract("transaction_detail_buyer_stock_limit"))
 * Variants find their endpoint by name; error bodies (or any contract on another endpoint)
 * name it: serveContract("error_404_not_found", { method: "get", path: "/api/transactions/:reference" }).
 * The status defaults to the endpoint's, or the one in an `error_NNN_` name.
 */
export function serveContract(
  name: string,
  target?: { method: Method; path: string; status?: number },
): HttpHandler {
  contract(name); // fail early on a typo
  const endpoint =
    target ??
    [...ENDPOINTS, ...DEMO_ENDPOINTS].find(
      (e) => e.contract === name || e.variants?.includes(name),
    );
  if (!endpoint) throw new Error(`Contract "${name}" has no default endpoint: pass a target`);
  const status = target?.status ?? statusOf(name) ?? endpoint.status;
  return serve(endpoint.method, endpoint.path, name, status);
}
