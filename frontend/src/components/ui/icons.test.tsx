import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Icon } from "./icons";

describe("icons", () => {
  it("shows the sun file from static/icons/svg", () => {
    const { container } = render(<Icon name="sun" />);
    const image = container.querySelector("img");
    expect(image).not.toBeNull();
    expect(image?.getAttribute("src") ?? "").toMatch(/sun.*\.svg|data:image\/svg/);
  });
});