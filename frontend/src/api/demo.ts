import { apiGet, type RequestOptions } from "./client";
import type { DemoInboxMessage, DemoPersona } from "./types";

// Demo mode only: both answer 404 outside it, as if they did not exist. Both are anonymous.

/** The personas the picker signs in as. A 404 means this is not a demo. */
export function listDemoPersonas(): Promise<DemoPersona[]> {
  return apiGet<DemoPersona[]>("/api/demo/personas");
}

/** The newest codes the demo SMS inbox "sent", newest first. */
export function listDemoInbox(options?: RequestOptions): Promise<DemoInboxMessage[]> {
  return apiGet<DemoInboxMessage[]>("/api/demo/inbox", options);
}
