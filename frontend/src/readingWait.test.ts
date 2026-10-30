import { describe, expect, it } from "vitest";
import { GENERAL_DAILY_TITLES, cleanForecastTitle, readingFace } from "./readingWait";

describe("readingWait", () => {
  it("cleans birth dates from daily forecast title and replaces generic titles with a 3-4 word phrase", () => {
    const fallback = cleanForecastTitle("Фон дня 23 февраля 2002 года");
    expect(GENERAL_DAILY_TITLES).toContain(fallback);
    expect(fallback.split(/\s+/).length).toBeGreaterThanOrEqual(3);
    expect(fallback.split(/\s+/).length).toBeLessThanOrEqual(4);

    expect(cleanForecastTitle("Фон дня: 23 февраля 2002 года")).toBe(fallback);
    expect(cleanForecastTitle("23 февраля 2002 года")).toBe(fallback);
    expect(cleanForecastTitle("Фон дня")).toBe(fallback);

    expect(cleanForecastTitle("Спокойный ритм дня")).toBe("Спокойный ритм дня");
    expect(cleanForecastTitle("Фон дня: фокус и ясность")).toBe("Фокус и ясность");
    expect(cleanForecastTitle("День для ясных решений")).toBe("День для ясных решений");
  });

  it("produces clean ready face with a 3-4 word phrase instead of birth date in title", () => {
    const face = readingFace(
      {
        status: "ready",
        title: "Фон дня 23 февраля 2002 года",
        body: "Хороший день для дел",
        greeting: null,
        user_sign: null,
        shared_facts: null,
        history_id: "hist-1",
        streak: null,
        replayed: false,
        reset_at: null,
      },
      false,
      false,
    );
    expect(face.phase).toBe("ready");
    if (face.phase === "ready") {
      expect(GENERAL_DAILY_TITLES).toContain(face.title);
      expect(face.body).toBe("Хороший день для дел");
    }
  });
});
