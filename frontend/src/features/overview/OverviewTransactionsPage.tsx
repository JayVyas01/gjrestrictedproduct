import { Loader, Stack, Tabs, Text, Title } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { useTransactions } from "@/api/hooks/transactions";
import type { TransactionFilters } from "@/api/transactions";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { TransactionList } from "@/features/transactions/TransactionList";

type Tab = "all" | "superintendentApproved";
const TABS: Tab[] = ["all", "superintendentApproved"];

function Results({ filters, basePath }: { filters: TransactionFilters; basePath: string }) {
  const { t } = useTranslation();
  const list = useTransactions(filters);
  if (list.isPending) return <Loader role="status" aria-label={t("common.loading")} />;
  if (list.isError) return <ErrorNotice error={list.error} />;
  if (list.data.length === 0) {
    return (
      <EmptyState
        title={t("transactions.empty")}
        body={t(filters.approved_by ? "overview.emptyApproved" : "overview.emptyBody")}
      />
    );
  }
  return (
    <TransactionList
      transactions={list.data}
      label={t("pages.overviewTransactions")}
      basePath={basePath}
      showChain
    />
  );
}

interface Props {
  /** Each transaction links to `${basePath}/${reference}`. */
  basePath: string;
}

// Every transaction the Head Authority or the Software Owner can see, read-only, with All and
// Superintendent-approved tabs (`?approved_by=superintendent` in the address and the request).
export function OverviewTransactionsPage({ basePath }: Props) {
  const { t } = useTranslation();
  const [search, setSearch] = useSearchParams();
  const active: Tab =
    search.get("approved_by") === "superintendent" ? "superintendentApproved" : "all";
  const filters: TransactionFilters =
    active === "superintendentApproved" ? { approved_by: "superintendent" } : {};

  return (
    <Stack>
      <Title order={1}>{t("pages.overviewTransactions")}</Title>
      <Text c="dimmed">{t("overview.readOnly")}</Text>
      <Tabs
        value={active}
        onChange={(value) =>
          setSearch(value === "superintendentApproved" ? { approved_by: "superintendent" } : {})
        }
      >
        <Tabs.List aria-label={t("transactions.filter")}>
          {TABS.map((tab) => (
            <Tabs.Tab key={tab} value={tab}>
              {t(`overview.${tab}`)}
            </Tabs.Tab>
          ))}
        </Tabs.List>
        {TABS.map((tab) => (
          <Tabs.Panel key={tab} value={tab} pt="md">
            {tab === active && <Results filters={filters} basePath={basePath} />}
          </Tabs.Panel>
        ))}
      </Tabs>
    </Stack>
  );
}
