import { describe, expect, it } from "vitest";

import { maskBirthDate } from "./birthDate";

describe("birth date mask", () => {
  it("inserts dots while the user types digits", () => {
    expect(maskBirthDate("")).toBe("");
    expect(maskBirthDate("0")).toBe("0");
    expect(maskBirthDate("02")).toBe("02");
    expect(maskBirthDate("021")).toBe("02.1");
    expect(maskBirthDate("0201")).toBe("02.01");
    expect(maskBirthDate("02011990")).toBe("02.01.1990");
    expect(maskBirthDate("02.01.1990")).toBe("02.01.1990");
    expect(maskBirthDate("32131990")).toBe("32.13.1990");
    expect(maskBirthDate("02.01.199099")).toBe("02.01.1990");
  });
});
