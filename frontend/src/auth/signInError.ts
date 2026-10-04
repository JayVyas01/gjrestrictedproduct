import type { TFunction } from "i18next";
import { ApiError } from "@/api/client";

/**
 * The text for a failed sign-in step. A 401 on the code step is a wrong code; on the password
 * step the server's own detail ("Invalid credentials") is shown as is.
 */
export function signInError(t: TFunction, error: unknown, step: "password" | "code"): string {
  if (!(error instanceof ApiError)) return t("errors.somethingWrong");
  if (error.status === 429) return t("errors.tooManyTries");
  if (error.status === 401 && step === "code") return t("errors.wrongCode");
  if (error.status >= 500 || !error.detail) return t("errors.somethingWrong");
  return error.detail;
}
