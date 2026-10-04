import { Alert, Badge, Card, Group, List, SimpleGrid, Text, ThemeIcon, Title } from "@mantine/core";
import { IconCheck, IconX } from "@tabler/icons-react";
import type { ParseKeys } from "i18next";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { LicenceCard } from "@/api/types";
import { ALLOWED_COLOR, NOT_ALLOWED_COLOR } from "@/theme";
import { DateText } from "./DateText";
import { Qty } from "./Qty";

function Allowance({ allowed, yes, no }: { allowed: boolean; yes: ParseKeys; no: ParseKeys }) {
  const { t } = useTranslation();
  const Icon = allowed ? IconCheck : IconX;
  return (
    <List.Item
      icon={
        <ThemeIcon size={20} radius="xl" color={allowed ? ALLOWED_COLOR : NOT_ALLOWED_COLOR}>
          <Icon size={14} aria-hidden />
        </ThemeIcon>
      }
    >
      {t(allowed ? yes : no)}
    </List.Item>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <Text size="sm" c="dimmed">
        {label}
      </Text>
      <Text fw={500}>{children}</Text>
    </div>
  );
}

function banner(licence: LicenceCard): ParseKeys | null {
  if (licence.status === "SUSPENDED") return "licence.suspended";
  if (licence.status === "REVOKED") return "licence.revoked";
  if (!licence.trading_permitted) return "licence.notValid";
  return null;
}

interface Props {
  licence: LicenceCard;
  /** The card title's heading level (3 under a page section heading). */
  titleOrder?: 2 | 3;
}

// What a licence lets its holder do: type and scope, the allowances as ticks and crosses with
// words, the limits and the validity; a banner when it can't be used (suspended, revoked, expired).
export function PermissionCard({ licence, titleOrder = 2 }: Props) {
  const { t } = useTranslation();
  const warning = banner(licence);
  const allowancesId = `allowances-${licence.licence_number}`;
  return (
    <Card withBorder padding="lg">
      <Group justify="space-between" align="flex-start">
        <div>
          <Title order={titleOrder} size="h3">
            {`${licence.licence_type}: ${licence.scope}`}
          </Title>
          <Text size="sm" c="dimmed">
            {t("licence.number", { number: licence.licence_number })}
          </Text>
        </div>
        <Badge
          variant="filled"
          tt="none"
          color={licence.status === "ACTIVE" ? ALLOWED_COLOR : NOT_ALLOWED_COLOR}
        >
          {t(`licence.status.${licence.status}`)}
        </Badge>
      </Group>
      {warning && (
        <Alert color="red" mt="md">
          {t(warning)}
        </Alert>
      )}
      <Text id={allowancesId} fw={500} mt="md">
        {t("licence.allowances")}
      </Text>
      <List spacing="xs" mt="xs" aria-labelledby={allowancesId}>
        <Allowance allowed={licence.may_buy} yes="licence.mayBuy" no="licence.mayNotBuy" />
        <Allowance allowed={licence.may_sell} yes="licence.maySell" no="licence.mayNotSell" />
        <Allowance
          allowed={licence.may_transport}
          yes="licence.mayTransport"
          no="licence.mayNotTransport"
        />
      </List>
      <SimpleGrid cols={{ base: 1, xs: 3 }} mt="md">
        <Fact label={t("licence.stockLimit")}>
          <Qty value={licence.max_stock_qty} unit={licence.unit} />
        </Fact>
        <Fact label={t("licence.perTransaction")}>
          <Qty value={licence.max_per_transaction_qty} unit={licence.unit} />
        </Fact>
        <Fact label={t("licence.validity")}>
          <DateText iso={licence.valid_from} /> {t("licence.to")}{" "}
          <DateText iso={licence.valid_to} />
        </Fact>
      </SimpleGrid>
    </Card>
  );
}
