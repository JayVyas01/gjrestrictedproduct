import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "@/App";

// Mock mode only: start the MSW worker before the app's first request. The dynamic import sits
// behind import.meta.env.DEV, which is false in `vite build`, so MSW is never bundled.
async function startMocks(): Promise<void> {
  if (import.meta.env.DEV && import.meta.env.VITE_MOCK_API === "1") {
    const { startMockWorker } = await import("@/mocks/browser");
    await startMockWorker();
  }
}

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

void startMocks().then(() => {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
