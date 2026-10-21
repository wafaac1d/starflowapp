import { expect, test } from "vitest";

import { invoiceGrantsPremium } from "./telegram";

test("invoice status does not grant premium", () => {
  for (const status of ["paid", "cancelled", "failed", "pending", "unavailable"]) {
    expect(invoiceGrantsPremium(status)).toBe(false);
  }
});
