import {
  Alert,
  Button,
  Group,
  List,
  Loader,
  NativeSelect,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { useId, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSubstances } from "@/api/hooks/catalogue";
import { useMyLicences } from "@/api/hooks/licensing";
import { useCheckSale } from "@/api/hooks/transactions";
import { ErrorNotice } from "@/components/ErrorNotice";
import type { SaleDraft } from "./draft";
import { sellableSubstances } from "./sellable";
import type { StepProps } from "./stepProps";
import { checkKey, checkPassed, draftCheckKey, goodsFieldErrors } from "./validation";

/** The two-step notice, shown after a passed check and again on the review. */
export function TwoStepNotice({ draft }: { draft: SaleDraft }) {
  const { t } = useTranslation();
  if (draft.check?.approval_chain !== "OFFICER_THEN_SUPERINTENDENT") return null;
  return <Text>{t("sale.twoStep")}</Text>;
}

// Step 2: what is sold and how much, then a live check against both licences and the stock.
export function GoodsStep({ draft, update, errors, setErrors }: StepProps) {
  const { t } = useTranslation();
  const substances = useSubstances();
  const licences = useMyLicences();
  const check = useCheckSale();
  const checkHelpId = useId();
  const checkErrorId = useId();

  const sellable = useMemo(
    () =>
      substances.data && licences.data ? sellableSubstances(substances.data, licences.data) : [],
    [substances.data, licences.data],
  );
  const unit = sellable.find((substance) => substance.code === draft.substanceCode)?.unit;

  if (substances.isPending || licences.isPending) {
    return <Loader size="sm" role="status" aria-label={t("common.loading")} />;
  }
  if (substances.isError || licences.isError) {
    return <ErrorNotice error={substances.error ?? licences.error} />;
  }
  if (sellable.length === 0) {
    return <Alert color="red">{t("sale.noSellable")}</Alert>;
  }

  // Any change to what was checked means checking again.
  const change = (patch: Partial<SaleDraft>) => {
    check.reset();
    update({ ...patch, check: null });
  };

  const run = () => {
    const fieldErrors = goodsFieldErrors(draft);
    setErrors({ substanceCode: undefined, quantity: undefined, check: undefined, ...fieldErrors });
    if (Object.keys(fieldErrors).length > 0) return;
    const sale = {
      buyer_gstin: draft.gstin,
      substance_code: draft.substanceCode,
      quantity: draft.quantity.trim(),
    };
    check.mutate(sale, {
      onSuccess: (result) =>
        update({
          check: result.ok ? { key: checkKey(sale), approval_chain: result.approval_chain } : null,
        }),
    });
  };

  // A refusal shows only while it is about what is on screen now.
  const refused =
    check.data &&
    !check.data.ok &&
    check.variables &&
    checkKey(check.variables) === draftCheckKey(draft)
      ? check.data.reasons
      : null;

  return (
    <Stack>
      <NativeSelect
        label={t("sale.substance")}
        description={t("sale.substanceHelp")}
        error={errors.substanceCode && t(errors.substanceCode)}
        value={draft.substanceCode}
        data={[
          { value: "", label: t("sale.chooseSubstance") },
          ...sellable.map((substance) => ({
            value: substance.code,
            label: t("sale.substanceOption", { name: substance.name, unit: substance.unit }),
          })),
        ]}
        onChange={(event) => {
          setErrors({ substanceCode: undefined, check: undefined });
          change({ substanceCode: event.currentTarget.value });
        }}
      />
      <TextInput
        label={unit ? t("sale.quantityIn", { unit }) : t("sale.quantity")}
        description={t("sale.quantityHelp")}
        error={errors.quantity && t(errors.quantity)}
        value={draft.quantity}
        inputMode="decimal"
        autoComplete="off"
        rightSection={unit ? <Text size="sm">{unit}</Text> : undefined}
        rightSectionPointerEvents="none"
        onChange={(event) => {
          setErrors({ quantity: undefined, check: undefined });
          change({ quantity: event.currentTarget.value });
        }}
      />
      <Stack gap={4}>
        <Group>
          <Button
            variant="outline"
            onClick={run}
            loading={check.isPending}
            aria-describedby={errors.check ? `${checkHelpId} ${checkErrorId}` : checkHelpId}
          >
            {t("sale.check")}
          </Button>
        </Group>
        <Text id={checkHelpId} size="sm" c="dimmed">
          {t("sale.checkHelp")}
        </Text>
        {errors.check && (
          <Text id={checkErrorId} size="sm" c="red.9">
            {t(errors.check)}
          </Text>
        )}
      </Stack>

      <div aria-live="polite">
        {checkPassed(draft) && (
          <Alert color="green">
            <Text fw={700}>{t("sale.checkOk")}</Text>
            <TwoStepNotice draft={draft} />
          </Alert>
        )}
        {refused && (
          <Alert color="red">
            <Text fw={700}>{t("sale.checkRefused")}</Text>
            <List mt="xs" size="sm">
              {refused.map((reason) => (
                <List.Item key={reason}>{reason}</List.Item>
              ))}
            </List>
          </Alert>
        )}
        <ErrorNotice error={check.error} />
      </div>
    </Stack>
  );
}
