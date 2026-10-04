import { Text, ThemeIcon, Timeline } from "@mantine/core";
import { IconCheck, IconClock, IconX } from "@tabler/icons-react";
import type { ParseKeys } from "i18next";
import { useTranslation } from "react-i18next";
import type { TimelineEvent } from "@/api/types";
import { ALLOWED_COLOR, NOT_ALLOWED_COLOR } from "@/theme";
import { DateText } from "./DateText";

type Step = TimelineEvent["step"];

const TITLES: Partial<Record<`${Step}_${TimelineEvent["outcome"]}`, ParseKeys>> = {
  SELLER_STARTED: "timeline.SELLER_STARTED",
  SELLER_CANCEL: "timeline.SELLER_CANCEL",
  BUYER_CONFIRM: "timeline.BUYER_CONFIRM",
  BUYER_REJECT: "timeline.BUYER_REJECT",
  OFFICER_APPROVE: "timeline.OFFICER_APPROVE",
  OFFICER_RECOMMEND: "timeline.OFFICER_RECOMMEND",
  OFFICER_REJECT: "timeline.OFFICER_REJECT",
  SUPERINTENDENT_APPROVE: "timeline.SUPERINTENDENT_APPROVE",
  SUPERINTENDENT_REJECT: "timeline.SUPERINTENDENT_REJECT",
};

const PENDING: Record<Step, ParseKeys> = {
  SELLER: "timeline.pending_SELLER",
  BUYER: "timeline.pending_BUYER",
  OFFICER: "timeline.pending_OFFICER",
  SUPERINTENDENT: "timeline.pending_SUPERINTENDENT",
};

function Bullet({ event }: { event: TimelineEvent }) {
  const stopped = event.outcome === "REJECT" || event.outcome === "CANCEL";
  const Icon = stopped ? IconX : IconCheck;
  return (
    <ThemeIcon radius="xl" size={22} color={stopped ? NOT_ALLOWED_COLOR : ALLOWED_COLOR}>
      <Icon size={14} aria-hidden />
    </ThemeIcon>
  );
}

interface Props {
  events: TimelineEvent[];
  /** The step that acts next, shown greyed out after the events. */
  pending?: Step | null;
}

// A transaction's progress, like a parcel tracker: each step with who acted, when (IST), the
// reason and comment when given, and the position holder for authorities. Changes are announced.
export function StatusTimeline({ events, pending = null }: Props) {
  const { t } = useTranslation();
  return (
    <Timeline
      active={events.length - 1}
      bulletSize={22}
      lineWidth={2}
      role="list"
      aria-label={t("timeline.label")}
      aria-live="polite"
    >
      {events.map((event) => (
        <Timeline.Item
          key={`${event.step}-${event.outcome}-${event.at}`}
          role="listitem"
          bullet={<Bullet event={event} />}
          title={
            <span data-title>
              {t(TITLES[`${event.step}_${event.outcome}`] ?? "timeline.other")}
            </span>
          }
        >
          <Text size="sm">{event.by}</Text>
          {event.held_by && (
            <Text size="sm" c="dimmed">
              {t("timeline.heldBy", { holder: event.held_by })}
            </Text>
          )}
          <Text size="sm" c="dimmed">
            <DateText iso={event.at} withTime />
          </Text>
          {event.reason && <Text size="sm">{t("timeline.reason", { reason: event.reason })}</Text>}
          {event.comment && (
            <Text size="sm">{t("timeline.comment", { comment: event.comment })}</Text>
          )}
        </Timeline.Item>
      ))}
      {pending && (
        <Timeline.Item
          role="listitem"
          data-pending="true"
          lineVariant="dashed"
          bullet={<IconClock size={14} aria-hidden />}
          title={
            <Text c="dimmed" span data-title>
              {t(PENDING[pending])}
            </Text>
          }
        />
      )}
    </Timeline>
  );
}
