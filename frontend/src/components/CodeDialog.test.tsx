import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { ApiError } from "@/api/client";
import type { Challenge } from "@/api/types";
import { contract } from "@/test/handlers";
import { renderWithProviders } from "@/test/render";
import { CodeDialog } from "./CodeDialog";

const WRONG_CODE = "That code didn't match. Check the SMS or send a new code.";
const FIRST = contract<Challenge>("decision_code");
const SECOND: Challenge = { challenge_id: "second-challenge" };

interface Setup {
  requestCode?: () => Promise<Challenge>;
  submit?: (input: { challenge_id: string; code: string }) => Promise<string>;
}

function setup({
  requestCode = vi.fn<() => Promise<Challenge>>().mockResolvedValue(FIRST),
  submit = vi
    .fn<(input: { challenge_id: string; code: string }) => Promise<string>>()
    .mockResolvedValue("approved"),
}: Setup = {}) {
  const onDone = vi.fn();
  const onClose = vi.fn();
  function Harness() {
    const [opened, setOpened] = useState(true);
    return (
      <CodeDialog
        opened={opened}
        onClose={() => {
          onClose();
          setOpened(false);
        }}
        title="Confirm your decision"
        requestCode={requestCode}
        submit={submit}
        onDone={onDone}
      />
    );
  }
  const result = renderWithProviders(<Harness />);
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  return { ...result, user, requestCode, submit, onDone, onClose };
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function typeCode(user: ReturnType<typeof userEvent.setup>, code: string) {
  await user.click(screen.getByLabelText("Digit 1 of 6"));
  await user.paste(code);
}

describe("CodeDialog", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("requests a code on opening, then submits it and reports the result", async () => {
    const { user, requestCode, submit, onDone, baseElement } = setup();
    expect(
      await screen.findByRole("dialog", { name: "Confirm your decision" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("The code expires in 5:00.")).toBeInTheDocument();
    expect(requestCode).toHaveBeenCalledOnce();
    expect(await axe(baseElement)).toHaveNoViolations();

    await typeCode(user, "123456");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(onDone).toHaveBeenCalledWith("approved"));
    expect(submit).toHaveBeenCalledWith({ challenge_id: FIRST.challenge_id, code: "123456" });
  });

  it("asks for all six digits before submitting", async () => {
    const { user, submit } = setup();
    await screen.findByText("The code expires in 5:00.");
    await typeCode(user, "123");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter all 6 digits.");
    expect(submit).not.toHaveBeenCalled();
  });

  it("a wrong code shows the 401 text and keeps the dialog open for another try", async () => {
    const detail = contract<{ detail: string }>("error_401_wrong_code").detail;
    const submit = vi
      .fn<(input: { challenge_id: string; code: string }) => Promise<string>>()
      .mockRejectedValueOnce(new ApiError(401, detail))
      .mockResolvedValueOnce("approved");
    const { user, onDone, baseElement } = setup({ submit });
    await screen.findByText("The code expires in 5:00.");
    await typeCode(user, "999999");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(WRONG_CODE);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText("Digit 1 of 6")).toHaveAccessibleDescription(WRONG_CODE);
    expect(onDone).not.toHaveBeenCalled();
    expect(await axe(baseElement)).toHaveNoViolations();

    await typeCode(user, "123456");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(onDone).toHaveBeenCalledWith("approved"));
  });

  it("other errors show the error notice", async () => {
    const detail = contract<{ detail: string }>("error_403_not_allowed").detail;
    const submit = vi
      .fn<(input: { challenge_id: string; code: string }) => Promise<string>>()
      .mockRejectedValue(new ApiError(403, detail));
    const { user } = setup({ submit });
    await screen.findByText("The code expires in 5:00.");
    await typeCode(user, "123456");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(detail);
  });

  it("a failed code request shows the error and offers a new code", async () => {
    const requestCode = vi
      .fn<() => Promise<Challenge>>()
      .mockRejectedValueOnce(new ApiError(429, ""))
      .mockResolvedValueOnce(FIRST);
    const { user } = setup({ requestCode });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many tries. Wait a minute and try again.",
    );
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Send a new code" }));
    expect(await screen.findByText("The code expires in 5:00.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("Send a new code requests another and submits with the new challenge", async () => {
    const requestCode = vi
      .fn<() => Promise<Challenge>>()
      .mockResolvedValueOnce(FIRST)
      .mockResolvedValueOnce(SECOND);
    const { user, submit } = setup({ requestCode });
    await screen.findByText("The code expires in 5:00.");
    await advance(90_000);
    expect(screen.getByText("The code expires in 3:30.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Send a new code" }));
    expect(await screen.findByText("The code expires in 5:00.")).toBeInTheDocument();
    expect(requestCode).toHaveBeenCalledTimes(2);
    await typeCode(user, "654321");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({ challenge_id: "second-challenge", code: "654321" }),
    );
  });

  it("when the countdown runs out, submitting is disabled until a new code is sent", async () => {
    const { user, submit } = setup();
    await screen.findByText("The code expires in 5:00.");
    await advance(299_000);
    expect(screen.getByText("The code expires in 0:01.")).toBeInTheDocument();
    await advance(1_000);
    expect(screen.getByRole("alert")).toHaveTextContent("This code has expired. Send a new code.");
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
    expect(submit).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Send a new code" }));
    expect(await screen.findByText("The code expires in 5:00.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeEnabled();
  });

  it("Escape closes the dialog", async () => {
    const { user, onClose } = setup();
    await screen.findByText("The code expires in 5:00.");
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("focus starts on the first digit and stays inside the dialog", async () => {
    const { user } = setup();
    await screen.findByText("The code expires in 5:00.");
    await waitFor(() => expect(screen.getByLabelText("Digit 1 of 6")).toHaveFocus());
    const dialog = screen.getByRole("dialog");
    for (let i = 0; i < 12; i += 1) {
      await user.tab();
      expect(dialog).toContainElement(document.activeElement as HTMLElement);
    }
  });
});
