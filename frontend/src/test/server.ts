import { setupServer } from "msw/node";

// The MSW server every test shares. Task 2 adds the contract-backed default handlers;
// a test overrides one endpoint with `server.use(...)`, and overrides reset after each test.
export const server = setupServer();
