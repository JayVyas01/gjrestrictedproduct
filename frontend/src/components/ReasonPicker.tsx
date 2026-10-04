import { Loader, Radio, Stack, Textarea } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { useReasonCodes } from "@/api/hooks/catalogue";
import type { ReasonKind } from "@/api/types";
import { ErrorNotice } from "./ErrorNotice";

export const COMMENT_MAX = 500;

/** The chosen reason; `needsComment` is the code's `requires_text` (OTHER). */
export interface ReasonValue {
  code: string;
  comment: string;
  needsComment: boolean;
}

export const EMPTY_REASON: ReasonValue = { code: "", comment: "", needsComment: false };

/** A reason is chosen, with a comment when its code requires one. */
export function reasonComplete(value: ReasonValue): boolean {
  return Boolean(value.code) && (!value.needsComment || value.comment.trim().length > 0);
}

interface Props {
  kind: ReasonKind;
  value: ReasonValue;
  onChange: (value: ReasonValue) => void;
  /** Codes left out unless listed in `showCodes` (STOCK_LIMIT applies only to the buyer's own problem). */
  hideCodes?: string[];
  showCodes?: string[];
  /** Show what is missing (after a submit attempt). */
  showErrors?: boolean;
}

const DEFAULT_HIDDEN = ["STOCK_LIMIT"];

// The reasons for a rejection or flag, loaded for its kind. A code that requires text (Other)
// reveals a required comment.
export function ReasonPicker({
  kind,
  value,
  onChange,
  hideCodes = DEFAULT_HIDDEN,
  showCodes = [],
  showErrors = false,
}: Props) {
  const { t } = useTranslation();
  const reasons = useReasonCodes(kind);
  if (reasons.isPending) return <Loader size="sm" aria-label={t("common.loading")} />;
  if (reasons.isError) return <ErrorNotice error={reasons.error} />;

  const shown = reasons.data.filter(
    (reason) => !hideCodes.includes(reason.code) || showCodes.includes(reason.code),
  );
  const choose = (code: string) => {
    const needsComment = shown.find((reason) => reason.code === code)?.requires_text ?? false;
    onChange({ code, comment: needsComment ? value.comment : "", needsComment });
  };

  return (
    <Stack gap="sm">
      <Radio.Group
        label={t("reasons.label")}
        value={value.code}
        onChange={choose}
        withAsterisk
        error={showErrors && !value.code ? t("reasons.choose") : undefined}
      >
        <Stack gap="xs" mt="xs">
          {shown.map((reason) => (
            <Radio key={reason.code} value={reason.code} label={reason.label} />
          ))}
        </Stack>
      </Radio.Group>
      {value.needsComment && (
        <Textarea
          label={t("reasons.comment")}
          description={t("reasons.commentHint")}
          required
          maxLength={COMMENT_MAX}
          autosize
          minRows={2}
          value={value.comment}
          onChange={(event) => onChange({ ...value, comment: event.currentTarget.value })}
          error={showErrors && !value.comment.trim() ? t("reasons.commentRequired") : undefined}
        />
      )}
    </Stack>
  );
}
