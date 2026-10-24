import { describe, expect, it } from "vitest";

import { eclipticLongitude, equalCusps, natalGrid, wheelPoint } from "./natalWheel";

describe("natal wheel", () => {
  it("places 0° Aries at the top and grows clockwise", () => {
    expect(wheelPoint(0, 20)).toEqual({ x: 50, y: 30 });
    expect(wheelPoint(90, 20).x).toBeCloseTo(70);
    expect(wheelPoint(90, 20).y).toBeCloseTo(50);
  });

  it("reads the fixture placements in the illustration's sign order", () => {
    expect(eclipticLongitude("Лев", "19°24′")).toBeCloseTo(139.4);
    expect(eclipticLongitude("Рыбы", "4°12′")).toBeCloseTo(334.2);
    expect(eclipticLongitude("Скорпион", "12°03′")).toBeCloseTo(222.05);
  });

  it("draws equal houses from the ascendant when the chart has no cusps", () => {
    const grid = natalGrid(undefined);
    expect(grid.cusps).toEqual(equalCusps(eclipticLongitude("Скорпион", "12°03′")));
    expect(grid.bodies.map((body) => body.id)).toEqual(["sun", "moon", "asc"]);
    expect(grid.aspects).toEqual([]);
    const joined = new Set(grid.figure.flatMap((link) => [link.start, link.end]));
    for (const cusp of grid.cusps) {
      expect(joined.has(cusp)).toBe(true);
    }
    expect(grid.figure.some((link) => link.start !== link.end)).toBe(true);
  });

  it("uses the chart cusps and aspects instead of the fixture", () => {
    const grid = natalGrid({
      planets: [
        { name: "солнце", longitude: 10 },
        { name: "луна", longitude: 100 },
      ],
      houseCusps: [15, 48, 76, 108, 141, 168, 195, 228, 255, 286, 314, 346],
    });
    expect(grid.cusps[0]).toBe(15);
    expect(grid.cusps).toHaveLength(12);
    expect(grid.bodies.map((body) => body.id)).toEqual(["солнце", "луна"]);
    expect(grid.aspects).toEqual([
      { id: "солнце-луна-square", from: "солнце", to: "луна", kind: "hard" },
    ]);
  });
});
