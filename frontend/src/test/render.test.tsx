import { screen } from "@testing-library/react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "./render";

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
