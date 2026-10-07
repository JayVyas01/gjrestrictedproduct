import { apiGet, apiPost, type RequestOptions } from "./client";
import type {
  Challenge,
  DemoInboxMessage,
  DemoPersona,
  DemoSignupCandidate,
  DemoSignupCompleted,
  DemoSignupForm,
} from "./types";

// Demo mode only: all answer 404 outside it, as if they did not exist. All are anonymous.

/** The personas the picker signs in as. A 404 means this is not a demo. */
export function listDemoPersonas(): Promise<DemoPersona[]> {
  return apiGet<DemoPersona[]>("/api/demo/personas");
}

/** The newest codes the demo SMS inbox "sent", newest first. */
export function listDemoInbox(options?: RequestOptions): Promise<DemoInboxMessage[]> {
  return apiGet<DemoInboxMessage[]>("/api/demo/inbox", options);
}

/** Party sign-up, step 1: the code goes to the phone on file of the GSTIN's licence. */
export function startDemoSignup(form: DemoSignupForm): Promise<Challenge> {
  return apiPost<Challenge>("/api/demo/signup/start", form);
}

/** Party sign-up, step 2: the code creates the account (not signed in yet). */
export function completeDemoSignup(
  challengeId: string,
  code: string,
): Promise<DemoSignupCompleted> {
  return apiPost<DemoSignupCompleted>("/api/demo/signup/complete", {
    challenge_id: challengeId,
    code,
  });
}

/** Licensed businesses with no account yet, for "Pick a demo business". */
export function listDemoSignupCandidates(): Promise<DemoSignupCandidate[]> {
  return apiGet<DemoSignupCandidate[]>("/api/demo/signup/candidates");
}
