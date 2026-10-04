import { Anchor, Button, Group, Loader, Stack, Table, Text, Title } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useHome } from "@/api/hooks/home";
import { useMyLicences, useMyStock } from "@/api/hooks/licensing";
import { useTransactions } from "@/api/hooks/transactions";
import { ErrorNotice } from "@/components/ErrorNotice";
import { PermissionCard } from "@/components/PermissionCard";
import { Loaded, Section } from "@/components/Section";
import { Qty } from "@/components/Qty";
import { WhatsNextCard } from "@/components/WhatsNextCard";
import { TransactionList } from "@/features/transactions/TransactionList";
import { AWAITING_PURCHASES_PATH, NEW_SALE_PATH, TRANSACTIONS_PATH } from "./paths";

const RECENT = 5;

function WhatsNext() {
  const { t } = useTranslation();
  const home = useHome();
  if (home.isPending) return <Loader size="sm" role="status" aria-label={t("common.loading")} />;
  if (home.isError) return <ErrorNotice error={home.error} />;
  const waiting = home.data.counts.awaiting_your_decision ?? 0;
  return waiting > 0 ? (
    <WhatsNextCard
      title={t("home.whatsNext")}
      body={t("home.awaiting", { count: waiting })}
      action={{ label: t("home.reviewPurchases"), to: AWAITING_PURCHASES_PATH }}
    />
  ) : (
    <WhatsNextCard
      title={t("home.whatsNext")}
      body={t("home.nothingWaiting")}
      action={{ label: t("home.startSale"), to: NEW_SALE_PATH }}
    />
  );
}

// The licensee's home: what waits for them, their licences, their stock and the latest
// transactions, with "New sale" as the primary action.
export function LicenseeHomePage() {
  const { t } = useTranslation();
  const licences = useMyLicences();
  const stock = useMyStock();
  const transactions = useTransactions();

  return (
    <Stack gap="xl">
      <Group justify="space-between">
        <Title order={1}>{t("pages.licenseeHome")}</Title>
        <Button component={Link} to={NEW_SALE_PATH}>
          {t("home.newSale")}
        </Button>
      </Group>

      <WhatsNext />

      <Section title={t("home.licences")}>
        <Loaded query={licences}>
          {(cards) =>
            cards.length === 0 ? (
              <Text c="dimmed">{t("home.noLicences")}</Text>
            ) : (
              cards.map((licence) => (
                <PermissionCard key={licence.licence_number} licence={licence} titleOrder={3} />
              ))
            )
          }
        </Loaded>
      </Section>

      <Section title={t("home.stock")}>
        <Loaded query={stock}>
          {(rows) =>
            rows.length === 0 ? (
              <Text c="dimmed">{t("home.noStock")}</Text>
            ) : (
              <Table aria-label={t("home.stock")} withTableBorder bg="white" maw={480}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th scope="col">{t("home.substance")}</Table.Th>
                    <Table.Th scope="col">{t("home.quantity")}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {rows.map((row) => (
                    <Table.Tr key={row.substance_code}>
                      <Table.Td>{row.substance}</Table.Td>
                      <Table.Td>
                        <Qty value={row.quantity} unit={row.unit} />
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )
          }
        </Loaded>
      </Section>

      <Section title={t("home.recent")}>
        <Loaded query={transactions}>
          {(list) =>
            list.length === 0 ? (
              <Text c="dimmed">{t("transactions.emptyBody")}</Text>
            ) : (
              <TransactionList
                transactions={list.slice(0, RECENT)}
                label={t("home.recent")}
                basePath={TRANSACTIONS_PATH}
              />
            )
          }
        </Loaded>
        <Anchor component={Link} to={TRANSACTIONS_PATH}>
          {t("home.allTransactions")}
        </Anchor>
      </Section>
    </Stack>
  );
}
