import { expect, type APIRequestContext, type Browser, type Page } from "@playwright/test";
import { csvRow } from "./demo-data";

// Sign-in budget: in demo mode an account may be sent 30 sign-in codes within 15 minutes before
// it is locked for 15 minutes (backend identity/login.py, A11); 5 wrong passwords lock it in
// every mode. A run signs each persona in a handful of times, well inside that, and a CI retry
// still fits. A spec that needs someone again later may keep them signed in in a second window
// (`signedInWindow`), as a presenter would.
//
// Sign-in is role first (owner decision A1): a party gives its GSTIN, an official their email.
// Officials' passwords are issued by the seed and must be changed at the first sign-in (A3):
// the first time a run signs an official in, `signInAs` saves `newPasswordFor(persona)` on the
// change-password page. The persona picker reads the current password from the backend, so
// later sign-ins use the new one without the tests keeping track.

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

/** The password an official persona chooses at their first sign-in of a run (deterministic). */
export function newPasswordFor(persona: PersonaKey): string {
  return `${persona}-New-2026!`;
}

/** Seeded buyers' GSTINs (synthetic: state code 99). */
export const GSTIN = {
  bopal: "99AAFCB2002B1Z6",
  sanandRetail: "99AAHCS4004D1Z8",
} as const;

/** Sanand Retail Wines: a seeded Licensee without a persona (signed in with `signInAsParty`). */
export const SANAND_RETAIL: Recipient = { name: "Sanand Retail Wines", last4: "0104" };

interface DemoPersona {
  key: string;
  role: string;
  identifier: string;
  password: string;
}

/** A persona as GET /api/demo/personas lists it now: role, identifier and current password. */
export async function personaAccount(
  request: APIRequestContext,
  persona: PersonaKey,
): Promise<DemoPersona> {
  const response = await request.get("/api/demo/personas");
  expect(response.ok(), `GET /api/demo/personas answered ${response.status()}`).toBe(true);
  const account = ((await response.json()) as DemoPersona[]).find((p) => p.key === persona);
  if (!account) throw new Error(`e2e: no demo persona ${persona}`);
  return account;
}

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

/**
 * On a code step (sign-in or sign-up): waits for the code sent to `who` since `after`, then
 * fills it in through the demo SMS inbox's "Use this code", as a presenter would.
 */
export async function fillCodeFromInbox(
  page: Page,
  who: Recipient,
  after: Set<string>,
): Promise<void> {
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
}

/**
 * Sign-in step 2, then the change-password page when the password was issued (an official's
 * first sign-in of the run): the current password is `current`, the new one `newPassword`.
 */
async function enterSignInCode(
  page: Page,
  who: Recipient,
  after: Set<string>,
  change?: { current: string; newPassword: string },
): Promise<void> {
  await fillCodeFromInbox(page, who, after);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => url.pathname !== "/sign-in");
  if (new URL(page.url()).pathname === "/change-password") {
    if (!change) throw new Error(`e2e: ${who.name} was asked to change an issued password`);
    await expect(page.getByRole("heading", { name: "Choose a new password" })).toBeVisible();
    await page.getByLabel("Current password", { exact: true }).fill(change.current);
    await page.getByLabel("New password", { exact: true }).fill(change.newPassword);
    await page.getByLabel("Confirm the new password", { exact: true }).fill(change.newPassword);
    await page.getByRole("button", { name: "Save the new password" }).click();
    await page.waitForURL((url) => url.pathname !== "/change-password");
  }
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

/**
 * Signs in through the persona picker (role, identifier and current password filled in) and the
 * demo SMS inbox, as a presenter would. An official's first sign-in of the run also chooses
 * `newPasswordFor(persona)`.
 */
export async function signInAs(page: Page, persona: PersonaKey): Promise<void> {
  const who = PERSONAS[persona];
  const { password } = await personaAccount(page.request, persona);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Demo: sign in as" })).toBeVisible();
  const after = await inboxSnapshot(page.request);
  await page.getByRole("button", { name: who.label, exact: true }).click();
  await enterSignInCode(page, who, after, {
    current: password,
    newPassword: newPasswordFor(persona),
  });
}

/**
 * Signs in by hand as Party with a GSTIN, for a business without a persona. The password is the
 * business's current one from demo-data/parties.csv unless given.
 */
export async function signInAsParty(
  page: Page,
  gstin: string,
  who: Recipient,
  password?: string,
): Promise<void> {
  const current = password ?? csvRow("parties.csv", "gstin", gstin)?.password;
  if (!current) throw new Error(`e2e: no password for ${gstin} in demo-data/parties.csv`);
  await page.goto("/");
  await page.getByRole("radio", { name: "Party" }).check();
  await page.getByLabel("GSTIN", { exact: true }).fill(gstin);
  await page.getByLabel("Password", { exact: true }).fill(current);
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
