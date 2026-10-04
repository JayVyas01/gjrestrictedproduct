import { describe, expect, it } from "vitest";
import type { Me, Position } from "@/api/types";
import { contract } from "@/test/handlers";
import { holdsDistrictPosition } from "./session";

const SUPERINTENDENT = contract<Me>("me_superintendent");

function holding(...levels: Position["level"][]): Me {
  const [position] = SUPERINTENDENT.positions;
  return { ...SUPERINTENDENT, positions: levels.map((level) => ({ ...position!, level })) };
}

describe("holdsDistrictPosition", () => {
  it("is true only for a district position, as the server requires", () => {
    expect(holdsDistrictPosition(holding("DISTRICT"))).toBe(true);
    expect(holdsDistrictPosition(holding("TALUKA", "DISTRICT"))).toBe(true);
    expect(holdsDistrictPosition(holding("STATE"))).toBe(false);
    expect(holdsDistrictPosition(holding("TALUKA"))).toBe(false);
    expect(holdsDistrictPosition(holding())).toBe(false);
  });
});
