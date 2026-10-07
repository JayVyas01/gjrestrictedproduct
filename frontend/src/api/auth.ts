import { apiGet, apiPost, ensureCsrf } from "./client";
import type {
  Challenge,
  LoginRole,
  LoginVerified,
  Me,
  PasswordChange,
  PasswordChanged,
} from "./types";

export { ensureCsrf };

export interface LoginStart {
  role: LoginRole;
  /** A party's GSTIN, or an official's email. */
  identifier: string;
  password: string;
}

/** Step 1: the role, its identifier and the password; the server sends a code by SMS. */
export function startLogin(body: LoginStart): Promise<Challenge> {
  return apiPost<Challenge>("/api/auth/login", body);
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

/** A new password (required first when the system issued the current one). */
export function changePassword(body: PasswordChange): Promise<PasswordChanged> {
  return apiPost<PasswordChanged>("/api/auth/password", body);
}
