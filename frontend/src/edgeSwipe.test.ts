import { describe, expect, it } from "vitest";

import { backTarget, isEdgeBackSwipe, rememberNavigation } from "./edgeSwipe";

describe("edge swipe", () => {
  it("keeps an in-app stack and returns home from a direct screen", () => {
    const home = rememberNavigation([], "a", "/", "POP");
    const chart = rememberNavigation(home, "b", "/chart", "PUSH");
    expect(backTarget(chart.length, "/chart")).toBe("history");
    const returned = rememberNavigation(chart, "a", "/", "POP");
    expect(returned).toEqual([{ key: "a", path: "/" }]);
    expect(backTarget(returned.length, "/")).toBe("stay");
    const direct = rememberNavigation([], "c", "/profile", "POP");
    expect(backTarget(direct.length, "/profile")).toBe("home");
    const reset = rememberNavigation(chart, "d", "/", "PUSH");
    expect(reset).toEqual([{ key: "d", path: "/" }]);
  });

  it("accepts a rightward drag that starts at the left edge", () => {
    expect(isEdgeBackSwipe(8, 90, 12)).toBe(true);
    expect(isEdgeBackSwipe(40, 120, 0)).toBe(false);
    expect(isEdgeBackSwipe(4, 40, 0)).toBe(false);
    expect(isEdgeBackSwipe(4, 100, 90)).toBe(false);
  });
});