import { screen } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import type { ReasonKind } from "@/api/types";
import { renderWithProviders } from "@/test/render";
import { EMPTY_REASON, ReasonPicker, reasonComplete, type ReasonValue } from "./ReasonPicker";

let latest: ReasonValue = EMPTY_REASON;

function Harness(props: { kind: ReasonKind; showCodes?: string[]; showErrors?: boolean }) {
  const [value, setValue] = useState<ReasonValue>(EMPTY_REASON);
  return (
    <ReasonPicker
      {...props}
      value={value}
      onChange={(next) => {
        latest = next;
        setValue(next);
      }}
    />
  );
}

describe("ReasonPicker", () => {
  beforeEach(() => {
    latest = EMPTY_REASON;
  });

  it("loads the reasons for its kind, hiding the stock limit by default", async () => {
    const { container } = renderWithProviders(<Harness kind="BUYER_REJECTION" />);
    const group = await screen.findByRole("radiogroup", { name: "Reason" });
    expect(group).toBeInTheDocument();
    expect(
      await screen.findByRole("radio", { name: "I did not place this order" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: /stock limit/ })).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("shows the stock limit when the parent says it applies", async () => {
    renderWithProviders(<Harness kind="BUYER_REJECTION" showCodes={["STOCK_LIMIT"]} />);
    expect(
      await screen.findByRole("radio", {
        name: "This would take me over my licence's stock limit",
      }),
    ).toBeInTheDocument();
  });

  it("loads the officer's reasons for the officer kind", async () => {
    renderWithProviders(<Harness kind="OFFICER_REJECTION" />);
    expect(
      await screen.findByRole("radio", { name: "Material weight mismatch" }),
    ).toBeInTheDocument();
  });

  it("choosing a reason reports it as complete", async () => {
    const { user } = renderWithProviders(<Harness kind="BUYER_REJECTION" />);
    await user.click(await screen.findByRole("radio", { name: "Wrong substance" }));
    expect(latest).toEqual({ code: "WRONG_SUBSTANCE", comment: "", needsComment: false });
    expect(reasonComplete(latest)).toBe(true);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("Other reveals a required comment of up to 500 characters", async () => {
    const { user, container } = renderWithProviders(<Harness kind="BUYER_REJECTION" />);
    await user.click(await screen.findByRole("radio", { name: "Other" }));
    const comment = screen.getByRole("textbox", { name: /Describe the reason/ });
    expect(comment).toBeRequired();
    expect(comment).toHaveAttribute("maxlength", "500");
    expect(reasonComplete(latest)).toBe(false);
    await user.type(comment, "Wrong paperwork");
    expect(latest).toEqual({ code: "OTHER", comment: "Wrong paperwork", needsComment: true });
    expect(reasonComplete(latest)).toBe(true);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("a blank comment is not complete", () => {
    expect(reasonComplete({ code: "OTHER", comment: "   ", needsComment: true })).toBe(false);
    expect(reasonComplete(EMPTY_REASON)).toBe(false);
  });

  it("with showErrors, links each error to its field", async () => {
    const { user } = renderWithProviders(<Harness kind="BUYER_REJECTION" showErrors />);
    expect(await screen.findByRole("radiogroup", { name: "Reason" })).toHaveAccessibleDescription(
      "Choose a reason.",
    );
    await user.click(screen.getByRole("radio", { name: "Other" }));
    expect(
      screen.getByRole("textbox", { name: /Describe the reason/ }),
    ).toHaveAccessibleDescription(/Describe the reason\./);
  });
});
