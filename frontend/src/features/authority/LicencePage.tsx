import { Anchor, Card, Loader, SimpleGrid, Stack, Table, Text, Title } from "@mantine/core";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { useLicence } from "@/api/hooks/licensing";
import type { LicenceCard, LicenceDetail } from "@/api/types";
import { DateText } from "@/components/DateText";
import { ErrorNotice } from "@/components/ErrorNotice";
import { PermissionCard } from "@/components/PermissionCard";
import { Section } from "@/components/Section";
import { LICENCES_PATH } from "./paths";

/** The permissions card's view of a register entry. */
function cardOf(licence: LicenceDetail): LicenceCard {
  return {
    licence_number: licence.licence_number,
    holder_name: licence.holder_name,
    licence_type: licence.licence_type,
    scope: licence.scope,
    status: licence.status,
    ...licence.permissions,
  };
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

function Licence({ licence }: { licence: LicenceDetail }) {
  const { t } = useTranslation();
  return (
    <>
      <Title order={1}>{licence.holder_name}</Title>
      <PermissionCard licence={cardOf(licence)} />
      <Section title={t("licenceDetail.details")}>
        <Card withBorder padding="md">
          <SimpleGrid cols={{ base: 1, xs: 2 }}>
            <Fact label={t("licenceDetail.gstin")}>{licence.gstin}</Fact>
            <Fact label={t("licenceDetail.area")}>{licence.area}</Fact>
          </SimpleGrid>
        </Card>
      </Section>
      <Section title={t("licenceDetail.periods")}>
        {licence.periods.length === 0 ? (
          <Text c="dimmed">{t("licenceDetail.noPeriods")}</Text>
        ) : (
          <Table.ScrollContainer minWidth={320}>
            <Table striped aria-label={t("licenceDetail.periods")}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th scope="col">{t("licenceDetail.startsOn")}</Table.Th>
                  <Table.Th scope="col">{t("licenceDetail.endsOn")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {licence.periods.map((period) => (
                  <Table.Tr key={`${period.starts_on}-${period.ends_on}`}>
                    <Table.Td>
                      <DateText iso={period.starts_on} />
                    </Table.Td>
                    <Table.Td>
                      <DateText iso={period.ends_on} />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Section>
    </>
  );
}

interface Props {
  /** The register (the back link). */
  listPath?: string;
}

// One register entry: the permissions card, the GSTIN, the area and every validity period. The
// register never sends the holder's contact or any stock figure, so neither can appear here.
export function LicencePage({ listPath = LICENCES_PATH }: Props) {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const licenceId = /^\d+$/.test(id) ? Number(id) : NaN;
  const valid = Number.isSafeInteger(licenceId);
  const licence = useLicence(valid ? licenceId : 0, valid);

  return (
    <Stack>
      <Anchor component={Link} to={listPath}>
        {t("licenceDetail.back")}
      </Anchor>
      {valid && licence.isSuccess ? (
        <Licence licence={licence.data} />
      ) : (
        <>
          <Title order={1}>{t("pages.licenceDetail")}</Title>
          {!valid ? (
            <ErrorNotice error={new ApiError(404, "")} />
          ) : licence.isError ? (
            <ErrorNotice error={licence.error} />
          ) : (
            <Loader role="status" aria-label={t("common.loading")} />
          )}
        </>
      )}
    </Stack>
  );
}
