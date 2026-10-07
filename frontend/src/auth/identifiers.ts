import { SIGN_IN_ROLES, type SignInRole } from "@/api/types";

/** A GSTIN: 2 digits, 5 letters, 4 digits, a letter, then 3 letters or digits (15 in all). */
export const GSTIN_FORMAT = /^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]{3}$/;

/** A GSTIN as typed: capitals, without spaces. */
export function normaliseGstin(value: string): string {
  return value.toUpperCase().replace(/\s+/g, "");
}

export function isSignInRole(role: unknown): role is SignInRole {
  return typeof role === "string" && (SIGN_IN_ROLES as readonly string[]).includes(role);
}

/** What sign-in's step 1 starts with: kept when coming back for a new code, or from sign-up. */
export interface SignInStart {
  role: SignInRole;
  identifier: string;
}

/**
 * Sign-in's router state (never the URL): sign-up's "Go to sign in" preselects Party and the
 * new GSTIN. Anything else in the state is ignored.
 */
export function signInStartFrom(state: unknown): SignInStart | null {
  if (!state || typeof state !== "object") return null;
  const { role, identifier } = state as Record<string, unknown>;
  if (!isSignInRole(role) || typeof identifier !== "string") return null;
  return {
    role,
    identifier: role === "PARTY" ? normaliseGstin(identifier) : identifier,
  };
}

/** The server's minimum (Django's MinimumLengthValidator); the server checks the other rules. */
export const MIN_PASSWORD_LENGTH = 12;
