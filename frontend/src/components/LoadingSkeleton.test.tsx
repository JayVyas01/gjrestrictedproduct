import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { renderWithProviders } from "@/test/render";
import { LoadingSkeleton } from "./LoadingSkeleton";

describe("LoadingSkeleton", () => {
  it("is announced as loading and draws placeholder lines", async () => {
    const { container } = renderWithProviders(<LoadingSkeleton lines={4} />);
    const status = await screen.findByRole("status", { name: "Loading…" });
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status.querySelectorAll(".mantine-Skeleton-root")).toHaveLength(4);
    expect(await axe(container)).toHaveNoViolations();
  });
});
