import { expect, test } from "@playwright/test";
import { signInAs, signOut } from "./helpers";

// Caddy serves the CSP from the D3 design §6 on every response, and the app runs under it: no
// page breaks a directive (no inline scripts, nothing from another origin).
const CSP =
  "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; " +
  "frame-ancestors 'none'; base-uri 'self'; form-action 'self'";

test("the app is served with the exact CSP and strict headers", async ({ page }) => {
  const response = await page.goto("/");
  const headers = response?.headers() ?? {};
  expect(headers["content-security-policy"]).toBe(CSP);
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("same-origin");
  expect(headers["server"]).toBeUndefined();

  const api = await page.request.get("/api/health");
  expect(api.headers()["content-security-policy"]).toBe(CSP);
});

test("the main pages raise no CSP violation", async ({ page }) => {
  const violations: string[] = [];
  page.on("console", (message) => {
    if (/Content Security Policy/i.test(message.text())) violations.push(message.text());
  });
  page.on("pageerror", (error) => violations.push(`page error: ${error.message}`));
  // The browser's own report of each violation, collected in the page.
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (event) => {
      console.error(`Content Security Policy violation: ${event.violatedDirective}`);
    });
  });

  // The demo sign-up page, before anyone signs in.
  await page.goto("/sign-up");
  await expect(page.getByRole("heading", { level: 1, name: "Sign up your business" })).toBeVisible();

  await signInAs(page, "buyer");
  for (const path of ["/licensee", "/licensee/transactions", "/licensee/sale/new"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  }
  await signOut(page);

  await signInAs(page, "licensing_authority");
  const authorityPages = ["/authority", "/authority/licences", "/authority/licence-types"];
  for (const path of [...authorityPages, "/rule-changes"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  }

  expect(violations).toEqual([]);
});
