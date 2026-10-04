import { Stack, Textarea, TextInput } from "@mantine/core";
import { useTranslation } from "react-i18next";
import type { StepProps } from "./stepProps";
import { MAX_LENGTH } from "./validation";

type TransportField = "transporterName" | "transporterId" | "vehicleNumber" | "route";

// Step 3: who carries the goods, in which vehicle, by which route. Sent only in the POST body.
export function TransportStep({ draft, update, errors, setErrors }: StepProps) {
  const { t } = useTranslation();

  const field = (name: TransportField, tidy: (value: string) => string = (value) => value) => ({
    value: draft[name],
    maxLength: MAX_LENGTH[name],
    error: errors[name] && t(errors[name]),
    autoComplete: "off",
    onChange: (event: { currentTarget: { value: string } }) => {
      setErrors({ [name]: undefined });
      update({ [name]: tidy(event.currentTarget.value) });
    },
  });

  return (
    <Stack>
      <TextInput
        label={t("sale.transporterName")}
        description={t("sale.transporterNameHelp")}
        {...field("transporterName")}
      />
      <TextInput
        label={t("sale.transporterId")}
        description={t("sale.transporterIdHelp")}
        {...field("transporterId")}
      />
      <TextInput
        label={t("sale.vehicle")}
        description={t("sale.vehicleHelp")}
        spellCheck={false}
        {...field("vehicleNumber", (value) => value.toUpperCase())}
      />
      <Textarea
        label={t("sale.route")}
        description={t("sale.routeHelp")}
        autosize
        minRows={2}
        {...field("route")}
      />
    </Stack>
  );
}
