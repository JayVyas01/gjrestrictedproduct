import { expect, test } from "@playwright/test";
import { PERSONAS, signInAs, signOut, withCode } from "./helpers";

// Demo scene 8, maker-checker: Head Authority B drafted a rule change (Retail Vendor, Spirits:
// stock limit 1,000 L to 1,500 L). B cannot decide it; Head Authority A approves it with a code,
// and the licence types show the new limit.
test("a rule change is decided by the other Head Authority officer", async ({ page }) => {
  const openChange = async () => {
    await page.goto("/rule-changes");
    await page
      .getByRole("table", { name: "Rule changes" })
      .getByRole("row")
      .filter({ hasText: "Retail Vendor" })
      .getByRole("link")
      .first()
      .click();
  };

  await signInAs(page, "head_authority_b");
  await openChange();
  await expect(
    page.getByText("Another Head Authority officer must decide this change."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
  await signOut(page);

  await signInAs(page, "head_authority_a");
  await openChange();
  const comparison = page.getByRole("table", { name: "Current and proposed values" });
  await expect(comparison.getByRole("row").filter({ hasText: "Stock limit" })).toContainText(
    "1,500",
  );
  await expect(comparison.getByRole("row").filter({ hasText: "Stock limit" })).toContainText(
    "1,000",
  );
  await withCode(page, PERSONAS.head_authority_a, () =>
    page.getByRole("button", { name: "Approve", exact: true }).click(),
  );
  await expect(page.getByRole("main").getByText("Approved", { exact: true }).first()).toBeVisible();
  await signOut(page);

  await signInAs(page, "licensing_authority");
  await page.goto("/authority/licence-types");
  await page.getByRole("button", { name: /^Retail Vendor/ }).click();
  const spirits = page
    .getByRole("table", { name: "Rules for Retail Vendor" })
    .getByRole("row")
    .filter({ hasText: "Spirits (class)" });
  await expect(spirits).toContainText("1,500 L");
});
