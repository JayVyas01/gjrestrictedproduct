import { expect, test } from "@playwright/test";
import { PERSONAS, signInAs, signOut, withCode } from "./helpers";

// Demo scene 7: the superintendent reviews an open batch of approved sales, flags one as
// "quantity unusually high" and signs the batch off; the approving officer is alerted.
test("the superintendent flags a sale and signs off the batch", async ({ page }) => {
  await signInAs(page, "superintendent");
  await page.getByRole("link", { name: "Batches" }).first().click();
  const open = page.getByRole("list", { name: "Batches" }).getByRole("listitem").filter({
    has: page.getByText("Open", { exact: true }),
  });
  await open.first().getByRole("link").click();
  await expect(page.getByRole("heading", { level: 1, name: /^Batch / })).toBeVisible();

  // Flag the first sale the officer approved (the superintendent's own approvals can't be).
  const flag = page.getByRole("button", { name: /^Flag / }).first();
  const reference = ((await flag.getAttribute("aria-label")) ?? "").replace(/^Flag /, "");
  expect(reference).not.toBe("");
  await flag.click();
  const dialog = page.getByRole("dialog", { name: `Flag ${reference}` });
  await dialog.getByRole("radio", { name: "Quantity unusually high" }).check();
  await dialog.getByLabel("Comment (optional)").fill("Higher than this buyer usually takes.");
  await dialog.getByRole("button", { name: "Flag transaction" }).click();
  await expect(dialog).toBeHidden();
  const row = page
    .getByRole("table", { name: "Transactions in this batch" })
    .getByRole("row")
    .filter({ hasText: reference });
  await expect(row).toContainText("Quantity unusually high");
  await expect(row.getByRole("button", { name: `Flag ${reference}` })).toHaveCount(0);

  await withCode(page, PERSONAS.superintendent, () =>
    page.getByRole("button", { name: "Sign off batch" }).click(),
  );
  await expect(page.getByRole("main").getByText("Signed", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/^Signed by /)).toBeVisible();
  await signOut(page);

  // The Area Officer who approved it gets the flag alert.
  await signInAs(page, "area_officer");
  await page.getByRole("button", { name: /^Alerts, \d+ unacknowledged$/ }).click();
  const alert = page
    .getByRole("dialog", { name: "Alerts" })
    .getByRole("listitem")
    .filter({ hasText: reference })
    .filter({ hasText: "Reason: Quantity unusually high" });
  await expect(alert).toBeVisible();
  await expect(alert.getByRole("button", { name: "Acknowledge", exact: true })).toBeVisible();
});
