import { Anchor, Stack, Title } from "@mantine/core";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { useTransaction } from "@/api/hooks/transactions";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { TransactionDetail } from "./TransactionDetail";

interface Props {
  /** The list this transaction belongs to (the back link). */
  listPath: string;
}

// The route for one transaction (`:reference` in the path): loads it and shows TransactionDetail.
export function TransactionPage({ listPath }: Props) {
  const { t } = useTranslation();
  const { reference = "" } = useParams();
  const transaction = useTransaction(reference);

  return (
    <Stack>
      <Anchor component={Link} to={listPath} size="sm">
        {t("transaction.back")}
      </Anchor>
      <Title order={1} tabIndex={-1}>
        {t("transaction.title", { reference })}
      </Title>
      {transaction.isPending ? (
        <LoadingSkeleton />
      ) : transaction.isError ? (
        <ErrorNotice error={transaction.error} />
      ) : (
        <TransactionDetail transaction={transaction.data} />
      )}
    </Stack>
  );
}
