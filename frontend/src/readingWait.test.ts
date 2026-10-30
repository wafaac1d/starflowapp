import { describe, expect, it } from "vitest";
import { cleanForecastTitle, readingFace } from "./readingWait";

describe("readingWait", () => {
  it("cleans birth dates from daily forecast title", () => {
    expect(cleanForecastTitle("Фон дня 23 февраля 2002 года")).toBe("Фон дня");
    expect(cleanForecastTitle("Фон дня: 23 февраля 2002 года")).toBe("Фон дня");
    expect(cleanForecastTitle("23 февраля 2002 года")).toBe("Фон дня");
    expect(cleanForecastTitle("Спокойный ритм дня")).toBe("Спокойный ритм дня");
    expect(cleanForecastTitle("Фон дня: фокус и ясность")).toBe("Фон дня: фокус и ясность");
  });

  it("produces clean ready face without birth date in title", () => {
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
      expect(face.title).toBe("Фон дня");
      expect(face.body).toBe("Хороший день для дел");
    }
  });
});
