import { describe, expect, it } from "vitest";

import { customEventOk } from "./customEvent";

describe("custom event", () => {
  it("keeps a real event and rejects noise", () => {
    expect(customEventOk("День рождения")).toBe(true);
    expect(customEventOk("встреча с мамой")).toBe(true);
    expect(customEventOk("аааа")).toBe(false);
    expect(customEventOk("asdf")).toBe(false);
    expect(customEventOk("ок")).toBe(false);
    expect(customEventOk("🎉 праздник")).toBe(false);
  });
});
