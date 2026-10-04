import { useTranslation } from "react-i18next";

const TIME_ZONE = "Asia/Kolkata";
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

const dateFormat = new Intl.DateTimeFormat("en-IN", {
  timeZone: TIME_ZONE,
  day: "numeric",
  month: "short",
  year: "numeric",
});
const dateTimeFormat = new Intl.DateTimeFormat("en-IN", {
  timeZone: TIME_ZONE,
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
});
// A plain calendar date ("2047-12-31") is that day wherever you are: format it in UTC.
const calendarFormat = new Intl.DateTimeFormat("en-IN", {
  timeZone: "UTC",
  day: "numeric",
  month: "short",
  year: "numeric",
});

/** "4 Oct 2026" or "4 Oct 2026, 5:22 pm", in IST. */
export function formatDate(iso: string, withTime = false): string {
  if (DATE_ONLY.test(iso)) return calendarFormat.format(new Date(`${iso}T00:00:00Z`));
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return (withTime ? dateTimeFormat : dateFormat).format(date);
}

interface Props {
  iso: string | null;
  withTime?: boolean;
}

// A date (and optionally the time) in India Standard Time, en-IN style.
export function DateText({ iso, withTime = false }: Props) {
  const { t } = useTranslation();
  if (!iso) return <span>{t("common.notSet")}</span>;
  return <time dateTime={iso}>{formatDate(iso, withTime)}</time>;
}
