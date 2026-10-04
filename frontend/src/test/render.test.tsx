import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { renderApp, renderWithProviders } from "./render";
import { server } from "./server";

function Probe() {
  const { t } = useTranslation();
  const { ref } = useParams();
  return (
    <p>
      {t("app.name")} {ref}
    </p>
  );
}

describe("renderWithProviders", () => {
  it("renders at the given route with translations and route params", () => {
    const { user } = renderWithProviders(<Probe />, {
      route: "/transactions/TX-1",
      path: "/transactions/:ref",
    });
    expect(screen.getByText("Gujarat Restricted Goods TX-1")).toBeInTheDocument();
    expect(user).toBeDefined();
  });
});

describe("renderApp", () => {
  it("keeps a handler the test set before renderApp ahead of the contract handlers", async () => {
    server.use(http.get("/api/licences/mine", () => HttpResponse.json([])));
    renderApp("/licensee", { contracts: ["me_licensee", "home_licensee"] });
    expect(await screen.findByText("You hold no licences.")).toBeInTheDocument();
  });
});
