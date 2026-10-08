import { expect, test } from "@playwright/test";
import {
  GSTIN,
  PERSONAS,
  bellCount,
  decide,
  sendSale,
  signInAs,
  signOut,
  signedInWindow,
  startSale,
  statusOf,
} from "./helpers";

// Demo scene 6: the buyer rejects a sale they did not order. The seller already has two buyer
// rejections in the last 30 days, so the Area Officer's alert says this is the 3rd.
test("a buyer rejection alerts the officer, who acknowledges it", async ({ browser, page }) => {
  // The Area Officer watches in a window of their own.
  const officer = await signedInWindow(browser, "area_officer");
  const before = await bellCount(officer);

  await signInAs(page, "seller");
  await startSale(page, { gstin: GSTIN.bopal, substance: "Vodka (L)", litres: 12 });
  await expect(page.getByText("This sale can go ahead.")).toBeVisible();
  const reference = await sendSale(page);
  await signOut(page);

  await signInAs(page, "buyer");
  await page.goto(`/licensee/transactions/${encodeURIComponent(reference)}`);
  await expect(statusOf(page, "Requires your approval")).toBeVisible();
  await decide(page, "Reject", { as: PERSONAS.buyer, reason: "I did not place this order" });
  await expect(statusOf(page, "Rejected by the buyer")).toBeVisible();
  await signOut(page);

  // The officer's bell lights up with one more alert, which names the pattern.
  await officer.reload();
  await expect.poll(() => bellCount(officer)).toBe(before + 1);
  await officer.getByRole("button", { name: /^Alerts, \d+ unacknowledged$/ }).click();
  const drawer = officer.getByRole("dialog", { name: "Alerts" });
  const alert = drawer.getByRole("listitem").filter({ hasText: reference });
  await expect(alert).toContainText("Reason: I did not place this order");
  await expect(alert).toContainText("3rd buyer rejection for this seller in the last 30 days");

  await alert.getByRole("button", { name: "Acknowledge", exact: true }).click();
  await alert.getByLabel("Note (optional)").fill("Called the buyer; checking with the seller.");
  await alert.getByRole("button", { name: "Acknowledge alert" }).click();
  await expect(alert.getByText("Acknowledged").first()).toBeVisible();
  await expect.poll(() => bellCount(officer)).toBe(before);
  await officer.context().close();
});
