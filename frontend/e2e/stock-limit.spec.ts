import { expect, test } from "@playwright/test";
import {
  GSTIN,
  PERSONAS,
  decide,
  sendSale,
  signInAs,
  signOut,
  startSale,
  statusOf,
} from "./helpers";

// The buyer decides on their own stock limit: the seller never sees the buyer's stock, the buyer
// is offered only Reject, and a stock-limit rejection raises no alert.
test("a sale over the buyer's stock limit can only be rejected, without an alert", async ({
  page,
}) => {
  // Bopal holds 440 L of Whisky against a 500 L limit; 70 L more is too much.
  await signInAs(page, "seller");
  await startSale(page, { gstin: GSTIN.bopal, substance: "Whisky (L)", litres: 70 });
  await expect(page.getByText("This sale can go ahead.")).toBeVisible();
  const reference = await sendSale(page);
  await signOut(page);

  await signInAs(page, "buyer");
  await page.goto(`/licensee/transactions/${encodeURIComponent(reference)}`);
  await expect(
    page.getByText(
      "Confirming would take your Whisky stock to 510 L, above your licence limit of 500 L. " +
        "You can only reject this sale.",
    ),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirm purchase" })).toHaveCount(0);
  await decide(page, "Continue to reject", { as: PERSONAS.buyer });
  await expect(statusOf(page, "Rejected by the buyer")).toBeVisible();
  await signOut(page);

  // No alert for this sale reaches the officer.
  await signInAs(page, "area_officer");
  await page.getByRole("button", { name: /^Alerts, \d+ unacknowledged$/ }).click();
  const drawer = page.getByRole("dialog", { name: "Alerts" });
  await expect(drawer.getByRole("listitem").first()).toBeVisible();
  await expect(drawer.getByRole("listitem").filter({ hasText: reference })).toHaveCount(0);
});
