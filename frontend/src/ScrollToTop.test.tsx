import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { ScrollToTop, scrollToTop } from "./ScrollToTop";

describe("ScrollToTop", () => {
  it("resets scroll on navigation", () => {
    const scrollToMock = vi.fn();
    window.scrollTo = scrollToMock;

    document.documentElement.scrollTop = 150;
    document.body.scrollTop = 150;

    render(
      <MemoryRouter initialEntries={["/first", "/second"]}>
        <ScrollToTop />
      </MemoryRouter>,
    );

    expect(scrollToMock).toHaveBeenCalledWith(0, 0);
    expect(document.documentElement.scrollTop).toBe(0);
    expect(document.body.scrollTop).toBe(0);
  });

  it("resets scroll when scrollToTop function is called directly", () => {
    const scrollToMock = vi.fn();
    window.scrollTo = scrollToMock;

    document.documentElement.scrollTop = 200;
    scrollToTop();

    expect(scrollToMock).toHaveBeenCalledWith(0, 0);
    expect(document.documentElement.scrollTop).toBe(0);
  });
});
