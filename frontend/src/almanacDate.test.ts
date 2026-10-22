import { describe, expect, it } from "vitest";

import { describeIso, monthDays, shiftMonth } from "./almanacDate";
import { resolveTheme } from "./theme";

describe("almanac dates", () => {
  it("lists every day of the selected month", () => {
    const days = monthDays("2026-10-22", "Europe/Moscow");
    const selected = describeIso("2026-10-22", "Europe/Moscow");
    expect(days).toHaveLength(31);
    expect(days[21]?.iso).toBe("2026-10-22");
    expect(selected.day).toBe(22);
    expect(selected.month).toBe("октябрь");
    expect(selected.weekday).toBe("четверг");
  });

  it("keeps a leap february at 29 days and the next one at 28", () => {
    expect(monthDays("2024-02-10", "Europe/Moscow")).toHaveLength(29);
    expect(monthDays("2026-02-10", "Europe/Moscow")).toHaveLength(28);
    expect(shiftMonth("2024-02-10", 1)).toBe("2024-03-01");
  });

  it("moves to the neighbouring month", () => {
    expect(shiftMonth("2026-10-22", 1)).toBe("2026-11-01");
    expect(shiftMonth("2026-01-02", -1)).toBe("2025-12-01");
  });
});

describe("theme", () => {
  it("keeps an explicit choice and otherwise follows telegram", () => {
    expect(resolveTheme("light", "dark", true)).toBe("light");
    expect(resolveTheme("telegram", "dark", false)).toBe("dark");
    expect(resolveTheme("telegram", null, true)).toBe("dark");
    expect(resolveTheme("telegram", null, false)).toBe("light");
  });
});