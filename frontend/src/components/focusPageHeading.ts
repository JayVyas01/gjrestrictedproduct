import { useCallback, useState } from "react";

/**
 * Moves the focus to the page's h1 (which carries tabIndex={-1}). Runs after the current render,
 * so a dialog that is closing has let go of the focus first.
 */
export function focusPageHeading(): void {
  window.setTimeout(() => {
    const main = document.getElementById("main");
    (main?.querySelector<HTMLElement>("h1") ?? document.querySelector<HTMLElement>("h1"))?.focus();
  }, 0);
}

/**
 * For a dialog whose action makes its own trigger go away (a decision, Flag, Withdraw, Cancel
 * sale, Sign off): once the action succeeds the dialog does not hand the focus back to the
 * trigger (pass `returnFocus` to the Modal), and the page heading takes it instead, so keyboard
 * and screen reader users are not dropped at the top of the document. Closing without acting
 * still returns the focus to the trigger.
 */
export function useFocusHeadingOnSuccess(opened: boolean) {
  const [succeeded, setSucceeded] = useState(false);
  const [lastOpened, setLastOpened] = useState(opened);
  // Each opening starts afresh. Adjusted during render, so the Modal never sees an opening
  // together with a stale `returnFocus={false}`.
  if (opened !== lastOpened) {
    setLastOpened(opened);
    if (opened) setSucceeded(false);
  }
  /** Call when the action succeeded, together with closing the dialog. */
  const succeed = useCallback(() => {
    setSucceeded(true);
    focusPageHeading();
  }, []);
  return { returnFocus: !succeeded, succeed };
}
