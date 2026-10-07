import { Stack, Tabs, Title } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { useTransactions } from "@/api/hooks/transactions";
import type { TransactionFilters } from "@/api/transactions";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { TransactionList } from "@/features/transactions/TransactionList";
import { NEW_SALE_PATH, TRANSACTIONS_PATH } from "./paths";

type Tab = "all" | "sales" | "purchases" | "waiting";
const TABS: Tab[] = ["all", "sales", "purchases", "waiting"];

const TAB_SEARCH: Record<Tab, Record<string, string>> = {
  all: {},
  sales: { side: "sales" },
  purchases: { side: "purchases" },
  waiting: { awaiting: "me" },
};

/** The list filters from the address; unknown values are ignored (the server would refuse them). */
export function filtersFrom(search: URLSearchParams): TransactionFilters {
  const side = search.get("side");
  return {
    awaiting: search.get("awaiting") === "me" ? "me" : undefined,
    side: side === "sales" || side === "purchases" ? side : undefined,
  };
}

function tabFor(filters: TransactionFilters): Tab {
  if (filters.awaiting === "me") return "waiting";
  return filters.side || "all";
}

function Results({ filters }: { filters: TransactionFilters }) {
  const { t } = useTranslation();
  const list = useTransactions(filters);
  if (list.isPending) return <LoadingSkeleton />;
  if (list.isError) return <ErrorNotice error={list.error} />;
  if (list.data.length === 0) {
    return filters.awaiting === "me" ? (
      <EmptyState title={t("transactions.empty")} body={t("transactions.emptyWaiting")} />
    ) : (
      <EmptyState
        title={t("transactions.empty")}
        body={t("transactions.emptyBody")}
        action={{ label: t("home.newSale"), to: NEW_SALE_PATH }}
      />
    );
  }
  return (
    <TransactionList
      transactions={list.data}
      label={t("pages.licenseeTransactions")}
      basePath={TRANSACTIONS_PATH}
    />
  );
}

// The licensee's transactions with All / Sales / Purchases / Waiting for you tabs. The filter
// lives in the address (`?side=`, `?awaiting=me`: no personal data), so it can be linked to.
export function LicenseeTransactionsPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useSearchParams();
  const filters = filtersFrom(search);
  const active = tabFor(filters);

  return (
    <Stack>
      <Title order={1}>{t("pages.licenseeTransactions")}</Title>
      <Tabs
        value={active}
        onChange={(value) => setSearch(TAB_SEARCH[(value as Tab | null) ?? "all"])}
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
