import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { STAR_LINK_LINES, STAR_LINK_TITLE, StarLink } from "./StarLink";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("StarLink", () => {
  it("shows the loader and walks the short lines", async () => {
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      media: "",
      addEventListener() {},
      removeEventListener() {},
    }));
    vi.useFakeTimers();
    render(<StarLink />);
    const first = STAR_LINK_LINES[0] ?? "";
    const second = STAR_LINK_LINES[1] ?? "";
    expect(document.querySelector("img")).toHaveAttribute("src", "/starflow_loader_hd.gif");
    expect(screen.getByRole("status")).toHaveTextContent(STAR_LINK_TITLE);
    expect(screen.getByText(first)).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2400);
    });
    expect(screen.getByText(second)).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2400 * (STAR_LINK_LINES.length - 1));
    });
    expect(screen.getByText(first)).toBeInTheDocument();
  });
});
