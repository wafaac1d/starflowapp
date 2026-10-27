import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it } from "vitest";

import { NOTICE_SLOTS, type NoticePrefs } from "../api/client";
import { text } from "../resources";
import { AdminPage } from "./AdminPage";
import { DeletePage } from "./DeletePage";
import { SettingsPage } from "./SettingsPage";

const prefs: NoticePrefs = {
  local_time: "09:00",
  timezone: "Europe/Moscow",
  day: false,
  moon: true,
  retro: false,
};

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  return input.url;
}

function renderPage(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("notice settings, deletion and admin", () => {
  afterEach(() => {
    cleanup();
  });

  it("offers half-hour slots and keeps the timezone as typed", async () => {
    expect(NOTICE_SLOTS).toHaveLength(48);
    expect(NOTICE_SLOTS).toContain("09:00");
    expect(NOTICE_SLOTS).toContain("09:30");
    expect(NOTICE_SLOTS).not.toContain("09:15");
    const fetchImpl = (async (input: RequestInfo | URL) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/notifications")) {
        return new Response(JSON.stringify(prefs), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("{}", { status: 404 });
    }) as typeof fetch;
    renderPage(<SettingsPage fetchImpl={fetchImpl} />);
    const zone = await screen.findByRole("textbox", { name: text("ui.settings.timezone") });
    expect(zone).toHaveClass("as-typed");
    expect(zone).toHaveValue("Europe/Moscow");
    expect(screen.getByRole("combobox")).toHaveValue("09:00");
    expect(screen.getByRole("checkbox", { name: text("ui.settings.moon") })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: text("ui.settings.day") })).not.toBeChecked();
  });

  it("keeps deletion disabled until the person confirms", async () => {
    renderPage(<DeletePage fetchImpl={fetch} />);
    const button = screen.getByRole("button", { name: text("ui.profile.delete_confirm") });
    expect(button).toBeDisabled();
    expect(screen.getByText(text("ui.delete.policy"))).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: text("ui.delete.confirm") }));
    expect(button).toBeEnabled();
  });

  it("hides admin actions from someone who is not an admin", () => {
    renderPage(<AdminPage isAdmin={false} />);
    expect(screen.getByText(text("ui.admin.denied"))).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: text("ui.admin.grant") })).not.toBeInTheDocument();
  });

  it("requires confirmation before a grant", async () => {
    const fetchImpl = (async (input: RequestInfo | URL) => {
      const url = requestUrl(input);
      if (url.includes("/admin/users")) {
        return new Response(JSON.stringify({ users: [], total: 0, page: 1, page_size: 10 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("{}", { status: 404 });
    }) as typeof fetch;
    renderPage(<AdminPage isAdmin fetchImpl={fetchImpl} />);
    const grant = await screen.findByRole("button", { name: text("ui.admin.grant") });
    expect(grant).toBeDisabled();
    expect(screen.queryByRole("button", { name: text("ui.admin.refund") })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(text("ui.admin.from"))).not.toBeInTheDocument();
    expect(screen.queryByText("secret-name")).not.toBeInTheDocument();
  });

  it("fills the premium grant from a listed person and clears it after success", async () => {
    const sent: unknown[] = [];
    let listed = 0;
    const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      if (url.includes("/admin/users")) {
        listed += 1;
        return new Response(
          JSON.stringify({
            users: [
              {
                user_id: "00000000-0000-0000-0000-000000000009",
                telegram_id: 8807,
                username: "maria",
                display_name: "Мария",
                premium: listed > 1,
              },
            ],
            total: 1,
            page: 1,
            page_size: 10,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/admin-grants")) {
        sent.push(JSON.parse(String(init?.body)));
        return new Response(null, { status: 204 });
      }
      return new Response("{}", { status: 404 });
    }) as typeof fetch;
    renderPage(<AdminPage isAdmin fetchImpl={fetchImpl} />);
    expect(await screen.findByText(/Мария/)).toBeInTheDocument();
    expect(screen.getByText(/@maria/)).toBeInTheDocument();
    expect(screen.getByText(/8807/)).toBeInTheDocument();
    expect(screen.getByText(/Без Premium/)).toBeInTheDocument();
    expect(screen.queryByText("1990-01-02")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: text("ui.admin.pick") }));
    const userField = screen.getByRole("textbox", { name: text("ui.admin.grant_user") });
    const reasonField = screen.getByRole("textbox", { name: text("ui.admin.reason") });
    expect(userField).toHaveValue("00000000-0000-0000-0000-000000000009");
    await userEvent.type(reasonField, "проверка");
    const grantConfirm = screen.getByRole("checkbox", { name: text("ui.admin.confirm") });
    await userEvent.click(grantConfirm);
    await userEvent.click(screen.getByRole("button", { name: text("ui.admin.grant") }));
    expect(sent).toEqual([
      {
        user_id: "00000000-0000-0000-0000-000000000009",
        days: 7,
        reason: "проверка",
        confirm: true,
      },
    ]);
    expect(
      await screen.findByRole("cell", { name: (value) => value === "Premium" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Без Premium/)).not.toBeInTheDocument();
    expect(userField).toHaveValue("");
    expect(reasonField).toHaveValue("");
    expect(grantConfirm).not.toBeChecked();
    expect(listed).toBeGreaterThan(1);
  });

  it("pages the user table", async () => {
    const fetchImpl = (async (input: RequestInfo | URL) => {
      const page = new URL(requestUrl(input), "http://starflow.local").searchParams.get("page");
      const first = page !== "2";
      const person = first
        ? {
            user_id: "00000000-0000-0000-0000-000000000001",
            telegram_id: 1,
            username: "first",
            display_name: "Первый",
            premium: true,
          }
        : {
            user_id: "00000000-0000-0000-0000-000000000002",
            telegram_id: 2,
            username: "second",
            display_name: "Второй",
            premium: false,
          };
      return new Response(
        JSON.stringify({ users: [person], total: 11, page: first ? 1 : 2, page_size: 10 }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }) as typeof fetch;
    renderPage(<AdminPage isAdmin fetchImpl={fetchImpl} />);
    expect(await screen.findByRole("columnheader", { name: text("ui.admin.col_name") })).toBeInTheDocument();
    expect(await screen.findByRole("cell", { name: "Первый" })).toBeInTheDocument();
    expect(screen.queryByRole("cell", { name: "Второй" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: text("ui.admin.page_prev") })).toBeDisabled();
    expect(screen.getByText("1 из 2")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: text("ui.admin.page_next") }));
    expect(await screen.findByRole("cell", { name: "Второй" })).toBeInTheDocument();
    expect(screen.queryByRole("cell", { name: "Первый" })).not.toBeInTheDocument();
    expect(screen.getByText("2 из 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: text("ui.admin.page_next") })).toBeDisabled();
  });
});
