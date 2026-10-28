import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { text } from "./resources";
import { resetWebAppCache } from "./telegram";

const initData = "auth_date=1&hash=abc";

function profile(step: string) {
  return {
    user_id: "00000000-0000-0000-0000-000000000001",
    is_admin: false,
    is_premium: false,
    step,
    display_name: null,
    birth_date: null,
    birth_time: null,
    birth_time_unknown: false,
    timezone: null,
    birth_place: null,
    latitude: null,
    longitude: null,
    calendar_sign: null,
    star_balance: 0,
  };
}

describe("entry", () => {
  beforeEach(() => {
    resetWebAppCache();
    delete window.Telegram;
    vi.unstubAllGlobals();
  });

  it("asks to open the app outside telegram", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: text("ui.open.title") })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: text("ui.home.lead") })).not.toBeInTheDocument();
  });

  it("exchanges initData in a header and opens the welcome step", async () => {
    window.Telegram = {
      WebApp: {
        initData,
        ready() {},
        expand() {},
      },
    };
    resetWebAppCache();
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(profile("welcome")), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    expect(await screen.findByRole("button", { name: "Начать" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Начать" }));
    expect(screen.getByRole("heading", { name: "Когда вы родились?" })).toBeInTheDocument();
    const call = fetchMock.mock.calls[0];
    expect(call).toBeDefined();
    const url = String(call?.[0]);
    const init = call?.[1];
    expect(url).toBe("/api/v1/session");
    expect(url).not.toContain(initData);
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe(`TMA ${initData}`);
    expect(headers.get("X-Starflow-Request")).toBe("1");
    expect(init?.credentials).toBe("include");
  });
});
