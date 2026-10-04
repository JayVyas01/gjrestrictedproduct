import type { LicenceCard, Substance } from "@/api/types";

/** A licence the holder can sell under today. */
function sellsToday(licence: LicenceCard): boolean {
  return licence.may_sell && licence.trading_permitted && licence.status === "ACTIVE";
}

/**
 * Does `licence` cover `substance`? The card names its scope and says what kind it is: a
 * substance licence names the substance, a class licence names the class.
 */
function covers(licence: LicenceCard, substance: Substance): boolean {
  return licence.scope_kind === "substance"
    ? licence.scope === substance.name
    : licence.scope === substance.substance_class;
}

/** The substances the seller may sell today under any of their licences, in catalogue order. */
export function sellableSubstances(substances: Substance[], licences: LicenceCard[]): Substance[] {
  const selling = licences.filter(sellsToday);
  return substances.filter((substance) => selling.some((licence) => covers(licence, substance)));
}
