import { Alert, Button, Card, Group, Stack, Text, TextInput } from "@mantine/core";
import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import { useLookupBuyer } from "@/api/hooks/transactions";
import { errorText } from "@/components/ErrorNotice";
import type { StepProps } from "./stepProps";
import { gstinError, MAX_LENGTH, normaliseGstin } from "./validation";

// Step 1: the buyer's GSTIN, looked up (in a POST body, never the URL) and confirmed by name.
export function BuyerStep({ draft, update, errors, setErrors }: StepProps) {
  const { t } = useTranslation();
  const lookup = useLookupBuyer();
  const input = useRef<HTMLInputElement>(null);

  // The name the lookup found, waiting for "Is this the right business?".
  const found = !draft.buyerName && lookup.isSuccess ? lookup.data.holder_name : null;

  const find = () => {
    const error = gstinError(draft.gstin);
    setErrors({ gstin: error });
    if (error) {
      input.current?.focus();
      return;
    }
    lookup.mutate(draft.gstin);
  };

  const change = () => {
    lookup.reset();
    update({ buyerName: "", check: null });
    input.current?.focus();
  };

  return (
    <Stack>
      <TextInput
        ref={input}
        label={t("sale.gstin")}
        description={t("sale.gstinHelp")}
        error={errors.gstin && t(errors.gstin)}
        value={draft.gstin}
        maxLength={MAX_LENGTH.gstin}
        autoComplete="off"
        spellCheck={false}
        styles={{ input: { textTransform: "uppercase" } }}
        onChange={(event) => {
          lookup.reset();
          setErrors({ gstin: undefined });
          update({ gstin: normaliseGstin(event.currentTarget.value), buyerName: "", check: null });
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            find();
          }
        }}
      />
      {!draft.buyerName && !found && (
        <Group>
          <Button variant="outline" onClick={find} loading={lookup.isPending}>
            {t("sale.findBuyer")}
          </Button>
        </Group>
      )}

      <div aria-live="polite">
        {lookup.isError && (
          <Alert color="red" role="alert">
            {lookup.error instanceof ApiError && lookup.error.status === 404 && lookup.error.detail
              ? lookup.error.detail
              : errorText(t, lookup.error)}
          </Alert>
        )}
        {(found ?? draft.buyerName) && (
          <Card withBorder>
            <Stack gap="xs">
              <Text size="sm" c="dimmed">
                {t("sale.registeredName")}
              </Text>
              <Text fw={700} size="lg">
                {found ?? draft.buyerName}
              </Text>
              {found ? (
                <>
                  <Text>{t("sale.rightBusiness")}</Text>
                  <Group>
                    <Button
                      onClick={() => {
                        setErrors({ gstin: undefined });
                        update({ buyerName: found });
                      }}
                    >
                      {t("sale.yes")}
                    </Button>
                    <Button variant="default" onClick={change}>
                      {t("sale.change")}
                    </Button>
                  </Group>
                </>
              ) : (
                <Group justify="space-between">
                  <Text c="green.9">{t("sale.buyerConfirmed")}</Text>
                  <Button variant="default" onClick={change}>
                    {t("sale.change")}
                  </Button>
                </Group>
              )}
            </Stack>
          </Card>
        )}
      </div>
    </Stack>
  );
}
