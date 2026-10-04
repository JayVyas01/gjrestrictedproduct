import {
  Button,
  Group,
  Loader,
  NativeSelect,
  Radio,
  Stack,
  Switch,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm, type UseFormReturnType } from "@mantine/form";
import type { TFunction } from "i18next";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useClasses, useLicenceTypes, useSubstances } from "@/api/hooks/catalogue";
import type { ProposalValues, ScopeKind } from "@/api/types";
import { ErrorNotice } from "@/components/ErrorNotice";
import { QUANTITY_PATTERN } from "@/features/sale/validation";

/** Same as NewLicenceTypePayload.code. */
export const CODE_PATTERN = /^[A-Z][A-Z0-9_]{1,31}$/;
export const JUSTIFICATION_MIN = 10;
export const JUSTIFICATION_MAX = 1000;
const NAME_MAX = 100;
const DESCRIPTION_MAX = 500;
const VALIDITY_PATTERN = /^\d{1,3}$/;

/** What each form hands over: the payload and the trimmed justification. */
export interface DraftValues {
  payload: ProposalValues;
  justification: string;
}

export interface DraftFormProps {
  onSubmit: (values: DraftValues) => void;
  submitting: boolean;
  /** The last draft's failure (a 422 lists the server's reasons). */
  error: unknown;
}

function justificationError(t: TFunction, value: string): string | null {
  const length = value.trim().length;
  return length < JUSTIFICATION_MIN || length > JUSTIFICATION_MAX
    ? t("draft.justificationLength")
    : null;
}

/** A quantity greater than 0 with up to 3 decimals (DecimalField(12, 3), min 0.001). */
function quantityError(t: TFunction, value: string): string | null {
  const trimmed = value.trim();
  return QUANTITY_PATTERN.test(trimmed) && Number(trimmed) > 0 ? null : t("draft.quantityInvalid");
}

interface WithJustification {
  justification: string;
}

function Justification<T extends WithJustification>({ form }: { form: UseFormReturnType<T> }) {
  const { t } = useTranslation();
  const length = form.getValues().justification.length;
  return (
    <Textarea
      label={t("draft.justification")}
      description={`${t("draft.justificationHint")} ${t("draft.justificationCount", { length })}`}
      autosize
      minRows={3}
      maxLength={JUSTIFICATION_MAX}
      required
      withAsterisk={false}
      {...form.getInputProps("justification")}
    />
  );
}

function FormShell({
  error,
  submitting,
  children,
  onSubmit,
}: {
  error: unknown;
  submitting: boolean;
  children: ReactNode;
  onSubmit: () => void;
}) {
  const { t } = useTranslation();
  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <Stack>
        <Title order={2} size="h3">
          {t("draft.details")}
        </Title>
        <ErrorNotice error={error} />
        {children}
        <Group>
          <Button type="submit" loading={submitting}>
            {t("draft.submit")}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

// A new licence type: code (capitalised as typed), name and an optional description.
export function LicenceTypeForm({ onSubmit, submitting, error }: DraftFormProps) {
  const { t } = useTranslation();
  const form = useForm({
    mode: "controlled",
    initialValues: { code: "", name: "", description: "", justification: "" },
    validate: {
      code: (value) => (CODE_PATTERN.test(value.trim()) ? null : t("draft.codeInvalid")),
      name: (value) => (value.trim() ? null : t("draft.nameRequired")),
      justification: (value) => justificationError(t, value),
    },
  });
  const submit = () => {
    if (form.validate().hasErrors) return;
    const values = form.getValues();
    onSubmit({
      payload: {
        code: values.code.trim(),
        name: values.name.trim(),
        description: values.description.trim(),
      },
      justification: values.justification.trim(),
    });
  };
  const code = form.getInputProps("code");

  return (
    <FormShell error={error} submitting={submitting} onSubmit={submit}>
      <TextInput
        label={t("draft.code")}
        description={t("draft.codeHint")}
        maxLength={32}
        autoComplete="off"
        spellCheck={false}
        required
        withAsterisk={false}
        {...code}
        onChange={(event) => form.setFieldValue("code", event.currentTarget.value.toUpperCase())}
      />
      <TextInput
        label={t("draft.name")}
        maxLength={NAME_MAX}
        required
        withAsterisk={false}
        {...form.getInputProps("name")}
      />
      <Textarea
        label={t("draft.description")}
        description={t("draft.descriptionHint")}
        maxLength={DESCRIPTION_MAX}
        autosize
        minRows={2}
        {...form.getInputProps("description")}
      />
      <Justification form={form} />
    </FormShell>
  );
}

interface ScopeValues {
  scopeKind: ScopeKind;
  scopeCode: string;
}

/** The substance or class chosen, as the payload names it (exactly one of the two). */
function scopePayload({ scopeKind, scopeCode }: ScopeValues): ProposalValues {
  return scopeKind === "substance" ? { substance_code: scopeCode } : { class_code: scopeCode };
}

function scopeError(t: TFunction, values: ScopeValues): string | null {
  if (values.scopeCode) return null;
  return t(values.scopeKind === "substance" ? "draft.substanceRequired" : "draft.classRequired");
}

/** The unit of the chosen scope, when it has one (a class of mixed units has none). */
function useScopeUnit({ scopeKind, scopeCode }: ScopeValues): string | null {
  const substances = useSubstances();
  const classes = useClasses();
  if (!scopeCode) return null;
  const list = scopeKind === "substance" ? substances.data : classes.data;
  return list?.find((item) => item.code === scopeCode)?.unit ?? null;
}

// The scope switch (a substance class or one substance) and the matching select.
function ScopeField<T extends ScopeValues>({ form }: { form: UseFormReturnType<T> }) {
  const { t } = useTranslation();
  const substances = useSubstances();
  const classes = useClasses();
  const { scopeKind } = form.getValues();
  const bySubstance = scopeKind === "substance";
  const query = bySubstance ? substances : classes;
  // Typed loosely: Mantine's path types can't see these keys through the generic T.
  const loose = form as unknown as UseFormReturnType<ScopeValues>;

  return (
    <>
      <Radio.Group
        label={t("draft.scopeKind")}
        value={scopeKind}
        onChange={(value) => {
          loose.setFieldValue("scopeKind", value as ScopeKind);
          loose.setFieldValue("scopeCode", "");
          loose.clearFieldError("scopeCode");
        }}
      >
        <Group gap="md" mt={4}>
          <Radio value="class" label={t("draft.scopeClass")} />
          <Radio value="substance" label={t("draft.scopeSubstance")} />
        </Group>
      </Radio.Group>
      {query.isPending ? (
        <Loader size="sm" role="status" aria-label={t("common.loading")} />
      ) : query.isError ? (
        <ErrorNotice error={query.error} />
      ) : (
        <NativeSelect
          key={scopeKind}
          label={t(bySubstance ? "draft.substance" : "draft.class")}
          required
          withAsterisk={false}
          data={[
            { value: "", label: t(bySubstance ? "draft.chooseSubstance" : "draft.chooseClass") },
            ...query.data.map((item) => ({
              value: item.code,
              label: item.unit ? `${item.name} (${item.unit})` : item.name,
            })),
          ]}
          {...loose.getInputProps("scopeCode")}
        />
      )}
    </>
  );
}

interface RuleVersionValues extends ScopeValues {
  licenceTypeCode: string;
  mayBuy: boolean;
  maySell: boolean;
  mayTransport: boolean;
  maxStock: string;
  maxPerTransaction: string;
  validityMonths: string;
  justification: string;
}

// A new rule version: the licence type, the scope, what it allows, the two limits (in the scope's
// unit), and the validity in months. The per-transaction limit can't exceed the stock limit.
export function RuleVersionForm({ onSubmit, submitting, error }: DraftFormProps) {
  const { t } = useTranslation();
  const licenceTypes = useLicenceTypes();
  const form = useForm<RuleVersionValues>({
    mode: "controlled",
    initialValues: {
      licenceTypeCode: "",
      scopeKind: "class",
      scopeCode: "",
      mayBuy: false,
      maySell: false,
      mayTransport: false,
      maxStock: "",
      maxPerTransaction: "",
      validityMonths: "",
      justification: "",
    },
    validate: {
      licenceTypeCode: (value) => (value ? null : t("draft.licenceTypeRequired")),
      scopeCode: (_value, values) => scopeError(t, values),
      maxStock: (value) => quantityError(t, value),
      maxPerTransaction: (value, values) => {
        const invalid = quantityError(t, value);
        if (invalid) return invalid;
        if (quantityError(t, values.maxStock)) return null;
        return Number(value) > Number(values.maxStock) ? t("draft.perTransactionAbove") : null;
      },
      validityMonths: (value) => {
        const trimmed = value.trim();
        const months = Number(trimmed);
        return VALIDITY_PATTERN.test(trimmed) && months >= 1 && months <= 120
          ? null
          : t("draft.validityInvalid");
      },
      justification: (value) => justificationError(t, value),
    },
  });
  const values = form.getValues();
  const unit = useScopeUnit(values);

  const submit = () => {
    if (form.validate().hasErrors) return;
    const v = form.getValues();
    onSubmit({
      payload: {
        licence_type_code: v.licenceTypeCode,
        ...scopePayload(v),
        may_buy: v.mayBuy,
        may_sell: v.maySell,
        may_transport: v.mayTransport,
        max_stock_qty: v.maxStock.trim(),
        max_per_transaction_qty: v.maxPerTransaction.trim(),
        validity_months: Number(v.validityMonths.trim()),
      },
      justification: v.justification.trim(),
    });
  };

  return (
    <FormShell error={error} submitting={submitting} onSubmit={submit}>
      {licenceTypes.isPending ? (
        <Loader size="sm" role="status" aria-label={t("common.loading")} />
      ) : licenceTypes.isError ? (
        <ErrorNotice error={licenceTypes.error} />
      ) : (
        <NativeSelect
          label={t("draft.licenceType")}
          required
          withAsterisk={false}
          data={[
            { value: "", label: t("draft.chooseLicenceType") },
            ...licenceTypes.data.map((type) => ({ value: type.code, label: type.name })),
          ]}
          {...form.getInputProps("licenceTypeCode")}
        />
      )}
      <ScopeField form={form} />
      <Stack gap="xs" role="group" aria-label={t("draft.allows")}>
        <Title order={3} size="h5">
          {t("draft.allows")}
        </Title>
        <Switch label={t("draft.mayBuy")} {...form.getInputProps("mayBuy", { type: "checkbox" })} />
        <Switch
          label={t("draft.maySell")}
          {...form.getInputProps("maySell", { type: "checkbox" })}
        />
        <Switch
          label={t("draft.mayTransport")}
          {...form.getInputProps("mayTransport", { type: "checkbox" })}
        />
      </Stack>
      <TextInput
        label={unit ? t("draft.stockLimitIn", { unit }) : t("draft.stockLimit")}
        description={t("draft.quantityHint")}
        inputMode="decimal"
        autoComplete="off"
        required
        withAsterisk={false}
        {...form.getInputProps("maxStock")}
      />
      <TextInput
        label={unit ? t("draft.perTransactionIn", { unit }) : t("draft.perTransaction")}
        description={t("draft.quantityHint")}
        inputMode="decimal"
        autoComplete="off"
        required
        withAsterisk={false}
        {...form.getInputProps("maxPerTransaction")}
      />
      <TextInput
        label={t("draft.validity")}
        description={t("draft.validityHint")}
        inputMode="numeric"
        autoComplete="off"
        maxLength={3}
        required
        withAsterisk={false}
        {...form.getInputProps("validityMonths")}
      />
      <Justification form={form} />
    </FormShell>
  );
}

interface ThresholdValues extends ScopeValues {
  quantity: string;
  justification: string;
}

// A new approval threshold: the scope and the quantity above which the superintendent approves.
export function ThresholdForm({ onSubmit, submitting, error }: DraftFormProps) {
  const { t } = useTranslation();
  const form = useForm<ThresholdValues>({
    mode: "controlled",
    initialValues: { scopeKind: "class", scopeCode: "", quantity: "", justification: "" },
    validate: {
      scopeCode: (_value, values) => scopeError(t, values),
      quantity: (value) => quantityError(t, value),
      justification: (value) => justificationError(t, value),
    },
  });
  const unit = useScopeUnit(form.getValues());

  const submit = () => {
    if (form.validate().hasErrors) return;
    const v = form.getValues();
    onSubmit({
      payload: { ...scopePayload(v), superintendent_above_qty: v.quantity.trim() },
      justification: v.justification.trim(),
    });
  };

  return (
    <FormShell error={error} submitting={submitting} onSubmit={submit}>
      <ScopeField form={form} />
      <TextInput
        label={unit ? t("draft.thresholdIn", { unit }) : t("draft.threshold")}
        description={t("draft.thresholdHint")}
        inputMode="decimal"
        autoComplete="off"
        required
        withAsterisk={false}
        {...form.getInputProps("quantity")}
      />
      <Justification form={form} />
    </FormShell>
  );
}
