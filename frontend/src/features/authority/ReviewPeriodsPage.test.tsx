import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { ReviewSetting } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderApp, renderWithProviders } from "@/test/render";
import { server } from "@/test/server";
import { ReviewPeriodsPage } from "./ReviewPeriodsPage";

const AS_AUTHORITY = ["me_licensing_authority", "home_licensing_authority"];
const SET = contract<ReviewSetting[]>("review_settings")[0]!;
const UNSET: ReviewSetting = {
  ...SET,
  position_id: SET.position_id + 1,
  title: "District Officer, Surat",
  area: "Surat",
  period_days: null,
  starts_on: null,
  current_period_end: null,
  last_batch_end: null,
};

/** Serves the two positions; the returned list records each PUT (its URL and body). */
function serveSettings() {
  let rows = [SET, UNSET];
  const puts: { url: string; body: unknown }[] = [];
  server.use(
    http.get("/api/oversight/review-settings", () => HttpResponse.json(rows)),
    http.put("/api/oversight/review-settings/:id", async ({ request, params }) => {
      const body = (await request.json()) as { period_days: number };
      puts.push({ url: new URL(request.url).pathname, body });
      const saved = { ...SET, period_days: body.period_days };
      rows = rows.map((row) => (row.position_id === Number(params.id) ? saved : row));
      return HttpResponse.json(saved);
    }),
  );
  return puts;
}

function rowFor(title: string): HTMLElement {
  const table = screen.getByRole("table", { name: "Review periods" });
  const row = within(table)
    .getAllByRole("row")
    .find((candidate) => within(candidate).queryByText(title));
  if (!row) throw new Error(`No row for ${title}`);
  return row;
}

describe("ReviewPeriodsPage", () => {
  it("lists each district position's period, start, current period end and last batch", async () => {
    serveSettings();
    const { container } = renderApp("/authority/review-periods", { contracts: AS_AUTHORITY });
    expect(
      await screen.findByRole("heading", { level: 1, name: "Review periods" }),
    ).toBeInTheDocument();
    await screen.findByRole("table", { name: "Review periods" });
    const set = rowFor(SET.title);
    expect(set).toHaveTextContent("15 days");
    expect(set).toHaveTextContent("14 Sept 2026");
    expect(set).toHaveTextContent("13 Oct 2026");
    expect(set).toHaveTextContent("28 Sept 2026");
    const unset = rowFor(UNSET.title);
    expect(unset).toHaveTextContent("Not set");
    expect(unset).toHaveTextContent("No batch yet");
    expect(
      within(set).getByRole("button", { name: `Change the review period for ${SET.title}` }),
    ).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("changes a period with an optional start date", async () => {
    const puts = serveSettings();
    const { user, container } = renderApp("/authority/review-periods", {
      contracts: AS_AUTHORITY,
    });
    await screen.findByRole("table", { name: "Review periods" });
    await user.click(
      within(rowFor(UNSET.title)).getByRole("button", { name: /Change the review period/ }),
    );
    const dialog = await screen.findByRole("dialog", {
      name: `Review period for ${UNSET.title}`,
    });
    expect(await axe(container)).toHaveNoViolations();

    // Nothing chosen yet: the period is required.
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(within(dialog).getByText("Choose 15, 30 or 60 days.")).toBeInTheDocument();
    expect(puts).toEqual([]);

    await user.click(within(dialog).getByRole("radio", { name: "30 days" }));
    await user.type(within(dialog).getByLabelText(/Start date/), "2026-09-01");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(puts).toEqual([
        {
          url: `/api/oversight/review-settings/${UNSET.position_id}`,
          body: { period_days: 30, starts_on: "2026-09-01" },
        },
      ]),
    );
    expect(await screen.findByText("Review period saved.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("sends no start date when it is left empty, starting from the current period", async () => {
    const puts = serveSettings();
    const { user } = renderApp("/authority/review-periods", { contracts: AS_AUTHORITY });
    await screen.findByRole("table", { name: "Review periods" });
    await user.click(within(rowFor(SET.title)).getByRole("button", { name: /Change/ }));
    const dialog = await screen.findByRole("dialog");
    // The current period is chosen already.
    expect(within(dialog).getByRole("radio", { name: "15 days" })).toBeChecked();
    await user.click(within(dialog).getByRole("radio", { name: "60 days" }));
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(puts.map((put) => put.body)).toEqual([{ period_days: 60 }]));
  });

  it("lists the reasons when the period can't be saved", async () => {
    serveSettings();
    server.use(
      http.put("/api/oversight/review-settings/:id", () =>
        HttpResponse.json(contract("error_422_review_setting"), { status: 422 }),
      ),
    );
    const { user, container } = renderApp("/authority/review-periods", {
      contracts: AS_AUTHORITY,
    });
    await screen.findByRole("table", { name: "Review periods" });
    await user.click(within(rowFor(SET.title)).getByRole("button", { name: /Change/ }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText(/Start date/), "2020-01-01");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    const alert = await within(dialog).findByRole("alert");
    expect(alert).toHaveTextContent("This review period can't be saved.");
    expect(within(alert).getByText(/The new period must start on/)).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("is read-only for the Head Authority and the Software Owner", async () => {
    serveSettings();
    const { container } = renderWithProviders(<ReviewPeriodsPage readOnly />);
    await screen.findByRole("table", { name: "Review periods" });
    expect(screen.queryByRole("button", { name: /Change/ })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("columnheader", { name: "Actions" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Only the Licensing Authority can change review periods."),
    ).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});
