import { describe, expect, it } from "vitest";
import type { LicenceCard, Substance } from "@/api/types";
import { contract } from "@/test/handlers";
import { sellableSubstances } from "./sellable";

const SUBSTANCES = contract<Substance[]>("catalogue_substances"); // Rum and Whisky, class Spirits
// Scope Spirits, scope_kind "class", unit L (the class's unit).
const CLASS_LICENCE = contract<LicenceCard[]>("licences_mine")[0] as LicenceCard;

const codes = (licences: LicenceCard[]) =>
  sellableSubstances(SUBSTANCES, licences).map((substance) => substance.code);

describe("sellableSubstances", () => {
  it("a class licence covers every substance in its class", () => {
    expect(codes([CLASS_LICENCE])).toEqual(["RUM", "WHISKY"]);
  });

  it("a substance licence covers only that substance", () => {
    expect(codes([{ ...CLASS_LICENCE, scope: "Whisky", scope_kind: "substance" }])).toEqual([
      "WHISKY",
    ]);
  });

  it("a substance licence does not cover a class of the same name", () => {
    expect(codes([{ ...CLASS_LICENCE, scope: "Spirits", scope_kind: "substance" }])).toEqual([]);
  });

  it("reads the scope kind, not the unit: a class licence has its class's unit", () => {
    expect(CLASS_LICENCE.unit).toBe("L");
    expect(codes([{ ...CLASS_LICENCE, unit: null }])).toEqual(["RUM", "WHISKY"]);
  });

  it("skips licences that may not sell, are not trading today, or are not active", () => {
    expect(codes([{ ...CLASS_LICENCE, may_sell: false }])).toEqual([]);
    expect(codes([{ ...CLASS_LICENCE, trading_permitted: false }])).toEqual([]);
    expect(codes([{ ...CLASS_LICENCE, status: "SUSPENDED" }])).toEqual([]);
  });

  it("covers nothing without licences", () => {
    expect(codes([])).toEqual([]);
  });
});
