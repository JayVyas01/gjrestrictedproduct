import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, expect } from "vitest";
import * as axeMatchers from "vitest-axe/matchers";
import { resetClientState } from "@/api/client";
import { server } from "./server";

expect.extend(axeMatchers);

// Any request without a handler fails the test, so no test can reach a real server.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
  sessionStorage.clear();
  resetClientState();
  document.cookie = "csrftoken=; path=/; max-age=0";
});
afterAll(() => server.close());

// jsdom lacks these browser APIs; Mantine needs them.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
window.ResizeObserver = ResizeObserverStub;

window.HTMLElement.prototype.scrollIntoView = () => {};

// jsdom has no canvas; axe-core probes it and would log "Not implemented" on every check.
window.HTMLCanvasElement.prototype.getContext = () => null;
