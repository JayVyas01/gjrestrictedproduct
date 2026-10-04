import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { ApiError } from "@/api/client";
import { contract } from "@/test/handlers";
import { renderWithProviders } from "@/test/render";
import { ErrorNotice } from "./ErrorNotice";

function shows(error: unknown) {
  renderWithProviders(<ErrorNotice error={error} />);
  return screen.findByRole("alert");
}

describe("ErrorNotice", () => {
  it("renders nothing without an error", async () => {
    renderWithProviders(<ErrorNotice error={null} />);
    await Promise.resolve();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("422 lists the server's reasons under its detail", async () => {
    const body = contract<{ detail: string; reasons: string[] }>("error_422_transaction_refused");
    const { container } = renderWithProviders(
      <ErrorNotice error={new ApiError(422, body.detail, { reasons: body.reasons })} />,
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(body.detail);
    expect(screen.getAllByRole("listitem").map((item) => item.textContent)).toEqual(body.reasons);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("400 with field errors points to the fields", async () => {
    const alert = await shows(new ApiError(400, "", { fieldErrors: { quantity: ["Too big."] } }));
    expect(alert).toHaveTextContent("Some answers need fixing. Check the fields marked below.");
  });

  it("401 is a wrong code", async () => {
    const body = contract<{ detail: string }>("error_401_wrong_code");
    expect(await shows(new ApiError(401, body.detail))).toHaveTextContent(
      "That code didn't match. Check the SMS or send a new code.",
    );
  });

  it("403 shows the server's detail, or a plain refusal without one", async () => {
    const body = contract<{ detail: string }>("error_403_not_allowed");
    expect(await shows(new ApiError(403, body.detail))).toHaveTextContent(body.detail);
  });

  it("403 without a detail says you can't do this", async () => {
    expect(await shows(new ApiError(403, ""))).toHaveTextContent("You can't do this.");
  });

  it("404 never reveals whether the record exists", async () => {
    const body = contract<{ detail: string }>("error_404_not_found");
    expect(await shows(new ApiError(404, body.detail))).toHaveTextContent(
      "Not found, or not yours to see.",
    );
  });

  it("409 shows the server's detail", async () => {
    const body = contract<{ detail: string }>("error_409_conflict");
    expect(await shows(new ApiError(409, body.detail))).toHaveTextContent(body.detail);
  });

  it("429 asks to wait", async () => {
    expect(await shows(new ApiError(429, ""))).toHaveTextContent(
      "Too many tries. Wait a minute and try again.",
    );
  });

  it("5xx and unknown failures say something went wrong, never a raw status", async () => {
    const alert = await shows(new ApiError(502, ""));
    expect(alert).toHaveTextContent("Something went wrong. Try again.");
    expect(alert).not.toHaveTextContent("502");
  });

  it("a network failure says something went wrong", async () => {
    expect(await shows(new TypeError("Failed to fetch"))).toHaveTextContent(
      "Something went wrong. Try again.",
    );
  });
});
