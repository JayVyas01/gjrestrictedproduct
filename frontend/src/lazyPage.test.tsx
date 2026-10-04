import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "@/test/render";
import { lazyPage } from "./lazyPage";

function Greeting({ name }: { name: string }) {
  return <h1>Hello {name}</h1>;
}

describe("lazyPage", () => {
  it("shows the loading skeleton while the page's code loads, then the page with its props", async () => {
    let resolve: (page: typeof Greeting) => void = () => {};
    const Page = lazyPage(() => new Promise<typeof Greeting>((done) => (resolve = done)));
    renderWithProviders(<Page name="Asha" />);
    expect(await screen.findByRole("status", { name: "Loading…" })).toBeInTheDocument();
    resolve(Greeting);
    expect(await screen.findByRole("heading", { name: "Hello Asha" })).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("loads the code once, however often the page is shown", async () => {
    let loads = 0;
    const Page = lazyPage(() => {
      loads += 1;
      return Promise.resolve(Greeting);
    });
    const { unmount } = renderWithProviders(<Page name="Asha" />);
    await screen.findByRole("heading", { name: "Hello Asha" });
    unmount();
    renderWithProviders(<Page name="Ravi" />);
    expect(await screen.findByRole("heading", { name: "Hello Ravi" })).toBeInTheDocument();
    expect(loads).toBe(1);
  });
});
