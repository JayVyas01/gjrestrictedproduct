import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { LicenceDetail, LicenceRegister, LicenceRow } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderApp, renderWithProviders } from "@/test/render";
import { server } from "@/test/server";
import { LicencesPage } from "./LicencesPage";

const AS_AUTHORITY = ["me_licensing_authority", "home_licensing_authority"];
const REGISTER = contract<LicenceRegister>("licences_register");
const ROW = REGISTER.results[0]!;
const DETAIL = contract<LicenceDetail>("licence_detail");
const NUMBER = "GJ/TEST/0001";
const GSTIN = "24ABCDE1234F1Z5";

/** 27 licences: 25 on page 1, 2 on page 2, as the server pages them. */
function serveRegister() {
  const rows: LicenceRow[] = Array.from({ length: 27 }, (_, i) => ({
    ...ROW,
    id: i + 1,
    licence_number: `GJ/TEST/${String(i + 1).padStart(4, "0")}`,
  }));
  const searches: string[] = [];
  server.use(
    http.get("/api/licences", ({ request }) => {
      const params = new URL(request.url).searchParams;
      searches.push(params.toString());
      const page = Number(params.get("page") ?? "1");
      const results = rows.slice((page - 1) * 25, page * 25);
      return HttpResponse.json({ count: rows.length, page, page_size: 25, results });
    }),
  );
  return searches;
}

/** Every request URL the app sends, and every POST body sent to the search. */
function recordRequests() {
  const urls: string[] = [];
  const bodies: unknown[] = [];
  const listener = ({ request }: { request: Request }) => {
    urls.push(request.url);
  };
  server.events.on("request:start", listener);
  server.use(
    http.post("/api/licences/search", async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(contract("licence_search"));
    }),
  );
  return { urls, bodies, stop: () => server.events.removeListener("request:start", listener) };
}

const forms = (value: string) => [value, encodeURIComponent(value), value.replaceAll("/", "%2F")];

describe("LicencesPage", () => {
  let stop: (() => void) | undefined;
  afterEach(() => stop?.());

  it("lists the register 25 a page, and pages through it", async () => {
    const searches = serveRegister();
    const { user, container } = renderApp("/authority/licences", { contracts: AS_AUTHORITY });
    expect(await screen.findByRole("heading", { level: 1, name: "Licences" })).toBeInTheDocument();
    expect(
      screen.getByText("Exact match only. Partial search isn't available, to protect licence holders."),
    ).toBeInTheDocument();

    const table = await screen.findByRole("table", { name: "Licences" });
    expect(within(table).getAllByRole("row")).toHaveLength(26); // a header and 25 rows
    expect(within(table).getByRole("link", { name: "GJ/TEST/0001" })).toHaveAttribute(
      "href",
      "/authority/licences/1",
    );
    expect(within(table).getAllByText("Retail: Spirits")).toHaveLength(25);
    expect(screen.getByText("1 to 25 of 27 licences")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Page 2" }));
    expect(await within(table).findByRole("link", { name: "GJ/TEST/0027" })).toBeInTheDocument();
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(screen.getByText("26 to 27 of 27 licences")).toBeInTheDocument();
    expect(searches).toEqual(["", "page=2"]);
  });

  it("filters by status, back on page 1", async () => {
    const searches = serveRegister();
    const { user } = renderApp("/authority/licences", { contracts: AS_AUTHORITY });
    await screen.findByRole("table", { name: "Licences" });
    await user.click(screen.getByRole("button", { name: "Page 2" }));
    await waitFor(() => expect(searches).toEqual(["", "page=2"]));
    await user.selectOptions(screen.getByLabelText("Status"), "SUSPENDED");
    await waitFor(() => expect(searches).toEqual(["", "page=2", "status=SUSPENDED"]));
  });

  it("searches by an exact licence number that never reaches a URL", async () => {
    serveRegister();
    const recorded = recordRequests();
    stop = recorded.stop;
    const { user, router, container } = renderApp("/authority/licences", {
      contracts: AS_AUTHORITY,
    });
    await screen.findByRole("table", { name: "Licences" });

    await user.type(screen.getByLabelText("Exact licence number"), NUMBER);
    await user.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => expect(recorded.bodies).toEqual([{ number: NUMBER }]));
    expect(await screen.findByText("1 to 1 of 1 licence")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    // By GSTIN as well.
    await user.click(screen.getByRole("radio", { name: "GSTIN" }));
    await user.clear(screen.getByLabelText("Exact GSTIN"));
    await user.type(screen.getByLabelText("Exact GSTIN"), GSTIN.toLowerCase());
    await user.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => expect(recorded.bodies).toHaveLength(2));
    expect(recorded.bodies[1]).toEqual({ gstin: GSTIN });

    const { pathname, search, hash } = router.state.location;
    const page = `${pathname}${search}${hash}`;
    expect(page).toBe("/authority/licences");
    for (const url of [page, ...recorded.urls]) {
      for (const value of [...forms(NUMBER), ...forms(GSTIN), GSTIN.toLowerCase()]) {
        expect(url).not.toContain(value);
      }
    }
    expect(recorded.urls.some((url) => url.endsWith("/api/licences/search"))).toBe(true);

    // Clearing the search goes back to the listing.
    await user.click(screen.getByRole("button", { name: "Clear search" }));
    expect(await screen.findByText("1 to 25 of 27 licences")).toBeInTheDocument();
  });

  it("asks for a value before searching", async () => {
    serveRegister();
    const recorded = recordRequests();
    stop = recorded.stop;
    const { user } = renderApp("/authority/licences", { contracts: AS_AUTHORITY });
    await screen.findByRole("table", { name: "Licences" });
    await user.click(screen.getByRole("button", { name: "Search" }));
    const field = screen.getByLabelText("Exact licence number");
    expect(field).toHaveAccessibleDescription(expect.stringContaining("Enter the licence number."));
    expect(recorded.bodies).toEqual([]);
  });

  it("says when no licence matches", async () => {
    serveRegister();
    server.use(
      http.post("/api/licences/search", () =>
        HttpResponse.json({ count: 0, page: 1, page_size: 25, results: [] }),
      ),
    );
    const { user, container } = renderApp("/authority/licences", { contracts: AS_AUTHORITY });
    await screen.findByRole("table", { name: "Licences" });
    await user.type(screen.getByLabelText("Exact licence number"), "GJ/TEST/9999");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("No licence found")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("links rows under another base path for the Head Authority and Software Owner", async () => {
    renderWithProviders(<LicencesPage basePath="/head/licences" />);
    const table = await screen.findByRole("table", { name: "Licences" });
    expect(within(table).getByRole("link", { name: ROW.licence_number })).toHaveAttribute(
      "href",
      `/head/licences/${ROW.id}`,
    );
  });
});

describe("LicencePage", () => {
  it("shows the permissions card, GSTIN, area and periods, and no contact or stock", async () => {
    server.use(
      http.get("/api/licences/:id", () =>
        HttpResponse.json({
          ...DETAIL,
          periods: [
            { starts_on: "2024-01-01", ends_on: "2025-12-31" },
            ...DETAIL.periods,
          ],
        }),
      ),
    );
    const { container } = renderApp(`/authority/licences/${DETAIL.id}`, {
      contracts: AS_AUTHORITY,
    });
    expect(
      await screen.findByRole("heading", { level: 1, name: DETAIL.holder_name }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Retail: Spirits" })).toBeInTheDocument();
    expect(screen.getByText("Can buy")).toBeInTheDocument();
    expect(screen.getByText("Cannot transport")).toBeInTheDocument();
    expect(screen.getByText(DETAIL.gstin)).toBeInTheDocument();
    expect(screen.getByText("Sanand")).toBeInTheDocument();

    const periods = screen.getByRole("table", { name: "Validity periods" });
    const [, older, current] = within(periods).getAllByRole("row");
    expect(older).toHaveTextContent("1 Jan 2024");
    expect(older).toHaveTextContent("31 Dec 2025");
    expect(current).toHaveTextContent("1 Jan 2026");
    expect(current).toHaveTextContent("31 Dec 2047");

    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/contact|mobile|phone|stock held|in stock/i);
    expect(screen.getByRole("link", { name: "Back to licences" })).toHaveAttribute(
      "href",
      "/authority/licences",
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("says when the licence isn't found", async () => {
    server.use(
      http.get("/api/licences/:id", () =>
        HttpResponse.json(contract("error_404_not_found"), { status: 404 }),
      ),
    );
    renderApp("/authority/licences/999", { contracts: AS_AUTHORITY });
    expect(await screen.findByText("Not found, or not yours to see.")).toBeInTheDocument();
  });
});
