import { describe, expect, it } from "vitest";

import { calendarSign, displayBirthDate } from "./calendarSign";

describe("calendarSign", () => {
  it("uses the same boundaries as the profile sign", () => {
    expect(calendarSign("12.08.1995")).toBe("лев");
    expect(calendarSign("03.05.1993")).toBe("телец");
    expect(calendarSign("01.01.2000")).toBe("козерог");
    expect(calendarSign("1995-08-12")).toBe("лев");
    expect(calendarSign("12.08")).toBeNull();
  });

  it("shows an iso date as day month year", () => {
    expect(displayBirthDate("1995-08-12")).toBe("12.08.1995");
    expect(displayBirthDate("12.08.1995")).toBe("12.08.1995");
  });
});
