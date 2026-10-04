const DECIMAL = /^(-?)(\d+)(?:\.(\d+))?$/;
const grouping = new Intl.NumberFormat("en-IN");

/**
 * A decimal string from the server ("150000.500") for display: Indian digit grouping, trailing
 * zeros dropped ("1,50,000.5"). Done on the digits, so no precision is lost to floating point.
 */
export function formatQuantity(value: string): string {
  const match = DECIMAL.exec(value.trim());
  if (!match) return value;
  const [, sign = "", whole = "0", fraction = ""] = match;
  const trimmed = fraction.replace(/0+$/, "");
  const grouped = grouping.format(BigInt(whole));
  return `${sign}${grouped}${trimmed ? `.${trimmed}` : ""}`;
}

interface Props {
  value: string;
  /** Null for a class scope with mixed units: the number is shown alone. */
  unit: string | null;
}

// A quantity, always with its unit when it has one.
export function Qty({ value, unit }: Props) {
  const text = formatQuantity(value);
  return <span>{unit ? `${text} ${unit}` : text}</span>;
}
