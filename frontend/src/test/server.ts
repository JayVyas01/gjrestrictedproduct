import { setupServer } from "msw/node";
import { handlers } from "./handlers";

// The MSW server every test shares, serving the contracts by default (src/test/handlers.ts).
// A test overrides one endpoint with `server.use(serveContract(...))` or its own handler;
// overrides reset after each test.
export const server = setupServer(...handlers);
