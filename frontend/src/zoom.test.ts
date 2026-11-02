import { describe, expect, it, vi } from "vitest";

import { preventZoom } from "./zoom";

describe("preventZoom", () => {
  it("prevents multi-touch touchmove and ctrl-wheel zoom", () => {
    preventZoom();

    const touchEvent = new Event("touchmove", { cancelable: true });
    Object.defineProperty(touchEvent, "touches", {
      value: [{}, {}],
    });
    document.dispatchEvent(touchEvent);
    expect(touchEvent.defaultPrevented).toBe(true);

    const singleTouchEvent = new Event("touchmove", { cancelable: true });
    Object.defineProperty(singleTouchEvent, "touches", {
      value: [{}],
    });
    document.dispatchEvent(singleTouchEvent);
    expect(singleTouchEvent.defaultPrevented).toBe(false);

    const wheelEvent = new Event("wheel", { cancelable: true });
    Object.defineProperty(wheelEvent, "ctrlKey", {
      value: true,
    });
    document.dispatchEvent(wheelEvent);
    expect(wheelEvent.defaultPrevented).toBe(true);

    const normalWheelEvent = new Event("wheel", { cancelable: true });
    Object.defineProperty(normalWheelEvent, "ctrlKey", {
      value: false,
    });
    document.dispatchEvent(normalWheelEvent);
    expect(normalWheelEvent.defaultPrevented).toBe(false);

    const keyEvent = new KeyboardEvent("keydown", {
      key: "+",
      ctrlKey: true,
      cancelable: true,
    });
    document.dispatchEvent(keyEvent);
    expect(keyEvent.defaultPrevented).toBe(true);
  });
});
