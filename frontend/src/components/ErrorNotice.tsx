import { Alert, List } from "@mantine/core";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";

/** The fix-it text for a failure (Global constraints, error table). Raw codes are never shown. */
export function errorText(t: TFunction, error: unknown): string {
  if (!(error instanceof ApiError)) return t("errors.somethingWrong");
  switch (error.status) {
    case 400:
      return error.fieldErrors ? t("errors.checkFields") : error.detail || t("errors.checkFields");
    case 401:
      return t("errors.wrongCode");
    case 403:
      return error.detail || t("errors.notAllowed");
    case 404:
      return t("errors.notFound");
    case 422:
      return error.detail || t("errors.refused");
    case 429:
      return t("errors.tooManyTries");
    default:
      if (error.status >= 500 || !error.detail) return t("errors.somethingWrong");
      return error.detail;
  }
}

interface Props {
  error: unknown;
}

// A failed request, in words the user can act on; a 422's reasons are listed as sent.
export function ErrorNotice({ error }: Props) {
  const { t } = useTranslation();
  if (!error) return null;
  const reasons = error instanceof ApiError && error.status === 422 ? error.reasons : undefined;
  return (
    <Alert color="red" role="alert">
      {errorText(t, error)}
      {reasons && reasons.length > 0 && (
        <List mt="xs" size="sm">
          {reasons.map((reason) => (
            <List.Item key={reason}>{reason}</List.Item>
          ))}
        </List>
      )}
    </Alert>
  );
}
