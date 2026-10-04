import { apiGet, apiPost, ensureCsrf } from "./client";
import type { Challenge, LoginVerified, Me } from "./types";

export { ensureCsrf };

/** Step 1: user ID and password; the server sends a code by SMS. */
export function startLogin(userId: string, password: string): Promise<Challenge> {
  return apiPost<Challenge>("/api/auth/login", { user_id: userId, password });
}

/** Step 2: the code from the SMS; signs in and starts the session. */
export function verifyLogin(challengeId: string, code: string): Promise<LoginVerified> {
  return apiPost<LoginVerified>("/api/auth/login/verify", { challenge_id: challengeId, code });
}

export function logout(): Promise<void> {
  return apiPost<void>("/api/auth/logout");
}

export function getMe(): Promise<Me> {
  return apiGet<Me>("/api/auth/me");
}
