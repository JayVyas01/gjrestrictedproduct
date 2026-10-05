import { expect, test } from "@playwright/test";
import {
  GSTIN,
  PERSONAS,
  SANAND_RETAIL,
  decide,
  sendSale,
  signInAs,
  signInWithUserId,
  signOut,
  signedInWindow,
  startSale,
  statusOf,
  stockOf,
} from "./helpers";

// Demo scenes 3 to 5: a 250 L Whisky sale is above the 200 L threshold, so after the buyer
// confirms and the Area Officer recommends it, the superintendent gives final approval and the
// stock moves.
test("a sale above the threshold needs the superintendent's final approval", async ({
  browser,
  page,
}) => {
  const retailUserId = process.env.E2E_RETAIL_USER_ID ?? "";
  expect(retailUserId, "set by global-setup.ts").not.toBe("");

  // The seller starts the sale in their own window; the check says the superintendent gives
  // final approval.
  const seller = await signedInWindow(browser, "seller");
  const sellerBefore = await stockOf(seller, "Whisky");
  await startSale(seller, { gstin: GSTIN.sanandRetail, substance: "Whisky (L)", litres: 250 });
  await expect(seller.getByText("This sale can go ahead.")).toBeVisible();
  await expect(
    seller.getByText("Above the threshold: the superintendent gives final approval."),
  ).toBeVisible();
  const reference = await sendSale(seller);
  await expect(statusOf(seller, "Waiting for the buyer")).toBeVisible();

  // The buyer confirms with an SMS code.
  await signInWithUserId(page, retailUserId, SANAND_RETAIL);
  const buyerBefore = await stockOf(page, "Whisky");
  await page.goto(`/licensee/transactions/${encodeURIComponent(reference)}`);
  await decide(page, "Confirm purchase", { as: SANAND_RETAIL });
  await expect(statusOf(page, "Waiting for the officer")).toBeVisible();
  await signOut(page);

  // The Area Officer can only recommend it upward (or reject it).
  await signInAs(page, "area_officer");
  await page.goto(`/personnel/transactions/${encodeURIComponent(reference)}`);
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
  await decide(page, "Recommend for approval", { as: PERSONAS.area_officer });
  await expect(statusOf(page, "Waiting for the superintendent")).toBeVisible();
  await signOut(page);

  // The superintendent gives final approval; the timeline shows every step.
  await signInAs(page, "superintendent");
  await page.goto(`/personnel/transactions/${encodeURIComponent(reference)}`);
  await decide(page, "Give final approval", { as: PERSONAS.superintendent });
  await expect(statusOf(page, "Approved")).toBeVisible();
  const timeline = page.getByRole("list", { name: "Progress" });
  await expect(timeline.getByRole("listitem")).toHaveCount(4);
  await expect(timeline.getByText("Superintendent approved")).toBeVisible();
  await signOut(page);

  // The stock moved on both homes.
  expect(await stockOf(seller, "Whisky")).toBe(sellerBefore - 250);
  await seller.context().close();
  await signInWithUserId(page, retailUserId, SANAND_RETAIL);
  expect(await stockOf(page, "Whisky")).toBe(buyerBefore + 250);
});
