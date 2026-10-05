import { expect, test } from "@playwright/test";
import { GSTIN, signInAs, startSale } from "./helpers";

// Demo scene 2: 250 L of Whisky is more than a hotel permit room may buy in one sale. The check
// says why in plain words, and the seller cannot go on.
test("a sale over the per-transaction limit is blocked with a plain reason", async ({ page }) => {
  await signInAs(page, "seller");
  await startSale(page, { gstin: GSTIN.bopal, substance: "Whisky (L)", litres: 250 });

  await expect(page.getByText("This sale can't go ahead:")).toBeVisible();
  await expect(
    page.getByText(
      "Quantity 250 L exceeds the buyer's licence's per-transaction limit of 200 L.",
    ),
  ).toBeVisible();

  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Check the sale before you continue.")).toBeVisible();
  await expect(page.getByText("Step 2 of 4")).toBeVisible();
  await expect(page.getByLabel("Transporter name")).toHaveCount(0);
});
