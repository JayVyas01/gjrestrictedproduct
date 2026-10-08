import { expect, test } from "@playwright/test";
import { csvRow } from "./demo-data";
import {
  fillCodeFromInbox,
  inboxSnapshot,
  newPasswordFor,
  personaAccount,
  signInAs,
  stockOf,
  type Recipient,
} from "./helpers";

// Padra Spirits Corner: licensed (an active spirits licence and a suspended beer one) but not
// signed up in the seed, so the demo sign-up offers it (backend/demo/dataset.py).
const BUSINESS = {
  name: "Padra Spirits Corner",
  gstin: "99ABACP1021W1Z7",
  licences: ["DEMO/VAD/0006", "DEMO/VAD/0007"],
};
// The sign-up code goes to the phone on file (…0121) before any account exists: the inbox
// names it "Enrolment". Once signed up, the business's own name.
const SIGN_UP_CODE: Recipient = { name: "Enrolment", last4: "0121" };
const PARTY: Recipient = { name: BUSINESS.name, last4: "0121" };
const EMAIL = "accounts@padra-spirits.example";
const PASSWORD = "Padra-Corner-2026!";

// Demo sign-up (owner decisions A4 and A5): a licensed business picks itself from the demo list,
// proves the phone on file with the code, signs in as Party with its GSTIN and finds every
// licence and its stock already there. parties.csv records the account straight away.
test("a licensed business signs up, signs in and appears in parties.csv", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Sign up", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Sign up your business" })).toBeVisible();
  expect(csvRow("parties.csv", "gstin", BUSINESS.gstin)?.signed_up).toBe("no");

  // "Pick a demo business" fills the GSTIN, the phone on file and the name.
  await page.getByRole("button", { name: new RegExp(`^Use ${BUSINESS.name}`) }).click();
  await expect(page.getByLabel("GSTIN", { exact: true })).toHaveValue(BUSINESS.gstin);
  await expect(page.getByLabel("Business name", { exact: true })).toHaveValue(BUSINESS.name);
  await page.getByLabel("Email", { exact: true }).fill(EMAIL);
  await page.getByLabel("Address", { exact: true }).fill("Station Road, Padra, Vadodara");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Confirm the password", { exact: true }).fill(PASSWORD);
  const sent = await inboxSnapshot(page.request);
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  await fillCodeFromInbox(page, SIGN_UP_CODE, sent);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Account created" })).toBeVisible();
  await expect(
    page.getByText(`Your account is ready. Sign in as Party with GSTIN ${BUSINESS.gstin}.`),
  ).toBeVisible();

  // Sign-in opens with Party chosen and the GSTIN filled in.
  await page.getByRole("button", { name: "Go to sign in" }).click();
  await expect(page.getByRole("radio", { name: "Party" })).toBeChecked();
  await expect(page.getByLabel("GSTIN", { exact: true })).toHaveValue(BUSINESS.gstin);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  const signIn = await inboxSnapshot(page.request);
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await fillCodeFromInbox(page, PARTY, signIn);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/licensee$/);

  // Every licence of the GSTIN, and so its stock, joined the account.
  for (const number of BUSINESS.licences) {
    await expect(page.getByText(`Licence ${number}`, { exact: true })).toBeVisible();
  }
  expect(await stockOf(page, "Whisky")).toBe(60);

  // parties.csv was rebuilt after the sign-up committed.
  await expect
    .poll(() => csvRow("parties.csv", "gstin", BUSINESS.gstin)?.signed_up)
    .toBe("yes");
  const row = csvRow("parties.csv", "gstin", BUSINESS.gstin);
  expect(row?.email).toBe(EMAIL);
  expect(row?.password).toBe(PASSWORD);
  expect(row?.licence_numbers).toBe(BUSINESS.licences.join("; "));
});

// A3 and A7: an official's issued password is replaced at the first sign-in, and officials.csv
// shows the new one with must_change_password=no. An official who has not signed in yet still
// shows yes.
test("officials.csv records an official's forced password change", async ({ page }) => {
  await signInAs(page, "licensing_authority");
  const { identifier: email, password } = await personaAccount(page.request, "licensing_authority");
  expect(password).toBe(newPasswordFor("licensing_authority"));

  // The file is rebuilt after the change commits: wait for it when this is the first sign-in.
  await expect
    .poll(() => csvRow("officials.csv", "email", email)?.must_change_password)
    .toBe("no");
  const row = csvRow("officials.csv", "email", email);
  expect(row?.login_role).toBe("LICENSING_AUTHORITY");
  expect(row?.must_change_password).toBe("no");
  expect(row?.password).toBe(newPasswordFor("licensing_authority"));

  const untouched = csvRow("officials.csv", "email", "officer.kalol@demo.gujarat.example");
  expect(untouched?.must_change_password).toBe("yes");
});
