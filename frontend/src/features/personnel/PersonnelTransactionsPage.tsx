import { Stack, Tabs, Title } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { useTransactions } from "@/api/hooks/transactions";
import type { TransactionFilters } from "@/api/transactions";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { TransactionList } from "@/features/transactions/TransactionList";
import { PERSONNEL_TRANSACTIONS_PATH } from "./paths";

type Tab = "all" | "waiting";
const TABS: Tab[] = ["all", "waiting"];

function Results({ filters }: { filters: TransactionFilters }) {
  const { t } = useTranslation();
  const list = useTransactions(filters);
  if (list.isPending) return <LoadingSkeleton />;
  if (list.isError) return <ErrorNotice error={list.error} />;
  if (list.data.length === 0) {
    return (
      <EmptyState
        title={t("transactions.empty")}
        body={t(filters.awaiting === "me" ? "transactions.emptyWaiting" : "transactions.emptyBody")}
      />
    );
  }
  return (
    <TransactionList
      transactions={list.data}
      label={t("pages.personnelTransactions")}
      basePath={PERSONNEL_TRANSACTIONS_PATH}
      showChain
    />
  );
}

// The transactions an officer or superintendent can see (their positions' areas, by RLS), with
// All / Waiting for you tabs. The filter lives in the address (`?awaiting=me`), so the home
// page's queue link opens on it.
export function PersonnelTransactionsPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useSearchParams();
  const active: Tab = search.get("awaiting") === "me" ? "waiting" : "all";
  const filters: TransactionFilters = active === "waiting" ? { awaiting: "me" } : {};

  return (
    <Stack>
      <Title order={1}>{t("pages.personnelTransactions")}</Title>
      <Tabs
        value={active}
        onChange={(value) => setSearch(value === "waiting" ? { awaiting: "me" } : {})}
      >
        <Tabs.List aria-label={t("transactions.filter")}>
          {TABS.map((tab) => (
            <Tabs.Tab key={tab} value={tab}>
              {t(`transactions.${tab}`)}
            </Tabs.Tab>
          ))}
        </Tabs.List>
        {TABS.map((tab) => (
          <Tabs.Panel key={tab} value={tab} pt="md">
            {tab === active && <Results filters={filters} />}
          </Tabs.Panel>
        ))}
      </Tabs>
    </Stack>
  );
}
