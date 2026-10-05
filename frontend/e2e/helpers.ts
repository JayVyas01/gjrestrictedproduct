import { expect, type APIRequestContext, type Browser, type Page } from "@playwright/test";

// Sign-in budget: an account that is sent 5 sign-in codes within 15 minutes is locked for 15
// minutes (backend identity/login.py, R10), demo or not. A whole run must stay within 4 sign-ins
// per account (so a CI retry still fits): a spec that needs someone again later keeps them
// signed in in a second window (`signedInWindow`) instead of signing in twice.

/** Who an SMS code goes to, as the demo inbox shows it: display name and the number's last 4. */
export interface Recipient {
  name: string;
  last4: string;
}

interface Persona extends Recipient {
  /** The persona picker's button. */
  label: string;
}

// The seeded personas (backend/demo/dataset.py). Both Head Authority officers are shown as
// "Head Authority" in the inbox; the last 4 digits tell them apart.
export const PERSONAS = {
  seller: { label: "Seller", name: "Sanand Spirits Pvt Ltd", last4: "0101" },
  buyer: { label: "Buyer", name: "Bopal Bar & Kitchen", last4: "0102" },
  area_officer: { label: "Area Officer (Sanand)", name: "Area Officer, Sanand", last4: "0011" },
  superintendent: {
    label: "Superintendent (Ahmedabad)",
    name: "Superintendent, Ahmedabad",
    last4: "0013",
  },
  licensing_authority: { label: "Licensing Authority", name: "Licensing Authority", last4: "0001" },
  head_authority_a: { label: "Head Authority A", name: "Head Authority", last4: "0002" },
  head_authority_b: { label: "Head Authority B", name: "Head Authority", last4: "0003" },
} as const satisfies Record<string, Persona>;

export type PersonaKey = keyof typeof PERSONAS;

/** Seeded buyers' GSTINs (synthetic: state code 99). */
export const GSTIN = {
  bopal: "99AAFCB2002B1Z6",
  sanandRetail: "99AAHCS4004D1Z8",
} as const;

/** Sanand Retail Wines: a seeded Licensee without a persona (see global-setup.ts). */
export const SANAND_RETAIL: Recipient = { name: "Sanand Retail Wines", last4: "0104" };

interface InboxMessage {
  display_name: string;
  contact_last4: string;
  code: string;
  created_at: string;
}

const keyOf = (message: InboxMessage) =>
  `${message.created_at}|${message.contact_last4}|${message.code}`;

async function inbox(request: APIRequestContext): Promise<InboxMessage[]> {
  const response = await request.get("/api/demo/inbox");
  expect(response.ok(), `GET /api/demo/inbox answered ${response.status()}`).toBe(true);
  return (await response.json()) as InboxMessage[];
}

/** The inbox as it is now: pass it to `codeFor` to wait for a code sent after this moment. */
export async function inboxSnapshot(request: APIRequestContext): Promise<Set<string>> {
  return new Set((await inbox(request)).map(keyOf));
}

function isFor(message: InboxMessage, who: string | Recipient): boolean {
  if (typeof who === "string") return message.display_name === who;
  return message.display_name === who.name && message.contact_last4 === who.last4;
}

/**
 * The latest code in the demo SMS inbox for this person (a display name, or a name and last 4).
 * With `after` (an `inboxSnapshot`), waits for a code that arrived since then.
 */
export async function codeFor(
  request: APIRequestContext,
  who: string | Recipient,
  after?: Set<string>,
): Promise<string> {
  let code = "";
  await expect
    .poll(
      async () => {
        const fresh = (await inbox(request)).find(
          (message) => isFor(message, who) && !after?.has(keyOf(message)),
        );
        code = fresh?.code ?? "";
        return code;
      },
      { message: `a code in the demo inbox for ${JSON.stringify(who)}`, intervals: [500, 1000] },
    )
    .toMatch(/^\d{6}$/);
  return code;
}

/** Sign-in step 2: the code arrives in the demo inbox; "Use this code" fills it in. */
async function enterSignInCode(page: Page, who: Recipient, after: Set<string>): Promise<void> {
  await expect(page.getByRole("group", { name: "One-time code" })).toBeVisible();
  const code = await codeFor(page.request, who, after);
  await page.getByRole("button", { name: "Open the Demo SMS inbox" }).click();
  const drawer = page.getByRole("dialog", { name: "Demo SMS inbox" });
  await drawer
    .getByRole("listitem")
    .filter({ hasText: code })
    .getByRole("button", { name: "Use this code" })
    .click();
  await expect(drawer).toBeHidden();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

/** Signs in through the persona picker and the demo SMS inbox, as a presenter would. */
export async function signInAs(page: Page, persona: PersonaKey): Promise<void> {
  const who = PERSONAS[persona];
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Demo: sign in as" })).toBeVisible();
  const after = await inboxSnapshot(page.request);
  await page.getByRole("button", { name: who.label, exact: true }).click();
  await enterSignInCode(page, who, after);
}

/** Signs in with a user ID and the demo password, for a seeded account without a persona. */
export async function signInWithUserId(page: Page, userId: string, who: Recipient): Promise<void> {
  const personas = await page.request.get("/api/demo/personas");
  const [{ password }] = (await personas.json()) as { password: string }[];
  await page.goto("/");
  await page.getByLabel("User ID").fill(userId);
  await page.getByLabel("Password").fill(password);
  const after = await inboxSnapshot(page.request);
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await enterSignInCode(page, who, after);
}

/**
 * A second browser window (its own cookies) signed in as `persona`, as a presenter would keep
 * one window per role open. Closed with the test.
 */
export async function signedInWindow(browser: Browser, persona: PersonaKey): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await signInAs(page, persona);
  return page;
}

export async function signOut(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Demo: sign in as" })).toBeVisible();
}

/**
 * Clicks `trigger`, which opens a code dialog, then types the code the inbox received for `who`
 * and confirms. Resolves once the dialog has closed (the action is done).
 */
export async function withCode(
  page: Page,
  who: Recipient,
  trigger: () => Promise<void>,
): Promise<void> {
  const after = await inboxSnapshot(page.request);
  await trigger();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("group", { name: "One-time code" })).toBeVisible();
  const code = await codeFor(page.request, who, after);
  for (const [index, digit] of [...code].entries()) {
    await dialog.getByLabel(`Digit ${index + 1} of 6`).fill(digit);
  }
  await dialog.getByRole("button", { name: "Confirm" }).click();
  await expect(dialog).toBeHidden();
}

interface DecideOptions {
  /** Whose code confirms the decision. */
  as: Recipient;
  /** For a rejection: the reason as listed, and a comment when the reason needs one. */
  reason?: string;
  comment?: string;
}

/**
 * A decision on the transaction page: the outcome button (e.g. "Confirm purchase", "Reject",
 * "Give final approval"), the reason for a rejection, then the code dialog through the inbox.
 * "Continue to reject" is for a reject form that is already open (a buyer over their limit).
 */
export async function decide(page: Page, button: string, opts: DecideOptions): Promise<void> {
  const rejecting = button === "Reject" || button === "Continue to reject";
  if (button === "Reject") await page.getByRole("button", { name: "Reject", exact: true }).click();
  if (opts.reason) await page.getByRole("radio", { name: opts.reason }).check();
  if (opts.comment) await page.getByLabel("Describe the reason").fill(opts.comment);
  const trigger = rejecting ? "Continue to reject" : button;
  await withCode(page, opts.as, () =>
    page.getByRole("button", { name: trigger, exact: true }).click(),
  );
}

/**
 * The unacknowledged-alerts count on the bell, read on a personnel home. The bell shows 0 until
 * the home counts arrive, so wait for the home's "What's next" first (it shows once they have).
 */
export async function bellCount(page: Page): Promise<number> {
  await expect(page.getByRole("heading", { name: "What's next" })).toBeVisible();
  const bell = page.getByRole("button", { name: /^Alerts, \d+ unacknowledged$/ });
  const label = (await bell.getAttribute("aria-label")) ?? "";
  return Number(/(\d+)/.exec(label)?.[1]);
}

export interface Sale {
  gstin: string;
  /** As in the substance list, e.g. "Whisky (L)". */
  substance: string;
  litres: number;
}

/** The seller's new-sale wizard up to the check on the Goods step. */
export async function startSale(page: Page, sale: Sale): Promise<void> {
  await page.getByRole("link", { name: "New sale" }).first().click();
  await expect(page.getByRole("heading", { name: "New sale", level: 1 })).toBeVisible();
  await page.getByLabel("Buyer's GSTIN").fill(sale.gstin);
  await page.getByRole("button", { name: "Find buyer" }).click();
  await page.getByRole("button", { name: "Yes, this is the buyer" }).click();
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Step 2 of 4")).toBeVisible();
  await page.getByLabel("Substance").selectOption({ label: sale.substance });
  await page.getByLabel(/^Quantity/).fill(String(sale.litres));
  await page.getByRole("button", { name: "Check", exact: true }).click();
}

/** Finishes a checked sale (transport and review) and returns its reference. */
export async function sendSale(page: Page): Promise<string> {
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByLabel("Transporter name").fill("Sabarmati Carriers");
  await page.getByLabel("ID or licence number").fill("GJ-TR-4411");
  await page.getByLabel("Vehicle number").fill("GJ01AB1234");
  await page.getByLabel("Route").fill("Sanand to the buyer via SG Highway");
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Send to buyer" }).click();
  await expect(page).toHaveURL(/\/licensee\/transactions\/[^/]+$/);
  return decodeURIComponent(page.url().split("/").pop() ?? "");
}

/** A transaction's status badge on its page. */
export function statusOf(page: Page, status: string) {
  return page.getByRole("main").getByText(status, { exact: true }).first();
}

/** A licensee's stock of one substance, in litres, from the "Your stock" table on their home. */
export async function stockOf(page: Page, substance: string): Promise<number> {
  await page.goto("/licensee");
  const row = page
    .getByRole("table", { name: "Your stock" })
    .getByRole("row")
    .filter({ has: page.getByRole("cell", { name: substance, exact: true }) });
  const quantity = await row.getByRole("cell").nth(1).innerText();
  return Number(quantity.replace(/[^\d.]/g, ""));
}
