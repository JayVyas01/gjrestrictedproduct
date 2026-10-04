import {
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  NativeSelect,
  Pagination,
  Radio,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useRegister } from "@/api/hooks/licensing";
import type { RegisterSearch } from "@/api/licensing";
import type { LicenceRegister, LicenceStatus } from "@/api/types";
import { DateText } from "@/components/DateText";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { ALLOWED_COLOR, NOT_ALLOWED_COLOR } from "@/theme";
import { LICENCES_PATH } from "./paths";

type Kind = "number" | "gstin";
const STATUSES: LicenceStatus[] = ["ACTIVE", "SUSPENDED", "REVOKED"];

/** A licence's status as a word on a badge: green when active, red otherwise. */
export function LicenceStatusBadge({ status }: { status: LicenceStatus }) {
  const { t } = useTranslation();
  return (
    <Badge
      variant="filled"
      tt="none"
      color={status === "ACTIVE" ? ALLOWED_COLOR : NOT_ALLOWED_COLOR}
    >
      {t(`licence.status.${status}`)}
    </Badge>
  );
}

interface SearchFormProps {
  searching: boolean;
  onSearch: (search: RegisterSearch) => void;
  onClear: () => void;
}

// The exact search. The value lives in this form's state and is sent in a POST body only: never
// in the page URL (router params) or a request URL.
function SearchForm({ searching, onSearch, onClear }: SearchFormProps) {
  const { t } = useTranslation();
  const [kind, setKind] = useState<Kind>("number");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) {
      setError(t(kind === "number" ? "register.numberRequired" : "register.gstinRequired"));
      return;
    }
    setError(null);
    onSearch({ [kind]: trimmed });
  };

  const clear = () => {
    setValue("");
    setError(null);
    onClear();
  };

  return (
    <Card withBorder padding="md" component="form" onSubmit={submit} noValidate role="search">
      <Stack gap="sm">
        <Title order={2} size="h4">
          {t("register.find")}
        </Title>
        <Radio.Group
          label={t("register.searchBy")}
          value={kind}
          onChange={(next) => {
            setKind(next as Kind);
            setError(null);
          }}
        >
          <Group gap="md" mt={4}>
            <Radio value="number" label={t("register.byNumber")} />
            <Radio value="gstin" label={t("register.byGstin")} />
          </Group>
        </Radio.Group>
        <TextInput
          label={t(kind === "number" ? "register.numberLabel" : "register.gstinLabel")}
          description={t(kind === "number" ? "register.numberHint" : "register.gstinHint")}
          value={value}
          error={error}
          maxLength={kind === "number" ? 40 : 15}
          autoComplete="off"
          spellCheck={false}
          onChange={(event) => {
            const next = event.currentTarget.value;
            setValue(kind === "gstin" ? next.toUpperCase() : next);
          }}
        />
        <Text size="sm" c="dimmed">
          {t("register.exactNote")}
        </Text>
        <Group gap="sm">
          <Button type="submit" loading={searching}>
            {t("register.search")}
          </Button>
          <Button variant="default" onClick={clear}>
            {t("register.clear")}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}

interface ResultsProps {
  register: LicenceRegister;
  basePath: string;
  onPage: (page: number) => void;
}

function Results({ register, basePath, onPage }: ResultsProps) {
  const { t } = useTranslation();
  const pages = Math.max(1, Math.ceil(register.count / register.page_size));
  const from = (register.page - 1) * register.page_size + 1;
  const to = from + register.results.length - 1;

  return (
    <Stack gap="sm">
      <Text size="sm" aria-live="polite">
        {t("register.showing", { from, to, count: register.count })}
      </Text>
      <Table.ScrollContainer minWidth={720}>
        <Table striped aria-label={t("register.table")}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th scope="col">{t("register.number")}</Table.Th>
              <Table.Th scope="col">{t("register.holder")}</Table.Th>
              <Table.Th scope="col">{t("register.typeScope")}</Table.Th>
              <Table.Th scope="col">{t("register.area")}</Table.Th>
              <Table.Th scope="col">{t("register.status")}</Table.Th>
              <Table.Th scope="col">{t("register.validTo")}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {register.results.map((row) => (
              <Table.Tr key={row.id}>
                <Table.Td>
                  <Anchor component={Link} to={`${basePath}/${row.id}`} fw={600}>
                    {row.licence_number}
                  </Anchor>
                </Table.Td>
                <Table.Td>{row.holder_name}</Table.Td>
                <Table.Td>
                  {t("register.typeScopeValue", { type: row.licence_type, scope: row.scope })}
                </Table.Td>
                <Table.Td>{row.area}</Table.Td>
                <Table.Td>
                  <LicenceStatusBadge status={row.status} />
                </Table.Td>
                <Table.Td>
                  <DateText iso={row.valid_to} />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {pages > 1 && (
        <nav aria-label={t("register.pages")}>
          <Pagination
            total={pages}
            value={register.page}
            onChange={onPage}
            withEdges
            getItemProps={(page) => ({ "aria-label": t("register.page", { page }) })}
            getControlProps={(control) => ({ "aria-label": t(`register.${control}`) })}
          />
        </nav>
      )}
    </Stack>
  );
}

interface Props {
  /** Each licence links to `${basePath}/${id}` (the Licensing Authority's register by default). */
  basePath?: string;
}

// The licence register: an exact search by licence number or GSTIN, a status filter and 25 rows a
// page. No actions, so the Head Authority and the Software Owner reuse it under their own path.
// There is no area filter yet: no endpoint lists the areas with their IDs (see the follow-ups).
export function LicencesPage({ basePath = LICENCES_PATH }: Props) {
  const { t } = useTranslation();
  const [search, setSearch] = useState<RegisterSearch>({});
  const [status, setStatus] = useState<LicenceStatus | "">("");
  const [page, setPage] = useState(1);
  const register = useRegister(
    { status: status || undefined, page: page > 1 ? page : undefined },
    search,
  );
  const searched = Boolean(search.number || search.gstin);

  return (
    <Stack>
      <Title order={1}>{t("pages.licences")}</Title>
      <SearchForm
        searching={register.isFetching && searched}
        onSearch={(next) => {
          setSearch(next);
          setPage(1);
        }}
        onClear={() => {
          setSearch({});
          setPage(1);
        }}
      />
      <NativeSelect
        label={t("register.status")}
        value={status}
        maw={280}
        data={[
          { value: "", label: t("register.allStatuses") },
          ...STATUSES.map((value) => ({ value, label: t(`licence.status.${value}`) })),
        ]}
        onChange={(event) => {
          setStatus(event.currentTarget.value as LicenceStatus | "");
          setPage(1);
        }}
      />
      {register.isPending ? (
        <Loader role="status" aria-label={t("common.loading")} />
      ) : register.isError ? (
        <ErrorNotice error={register.error} />
      ) : register.data.count === 0 ? (
        searched ? (
          <EmptyState title={t("register.noMatch")} body={t("register.noMatchBody")} />
        ) : (
          <EmptyState title={t("register.empty")} body={t("register.emptyBody")} />
        )
      ) : (
        <Results register={register.data} basePath={basePath} onPage={setPage} />
      )}
    </Stack>
  );
}
