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

  it("requires confirmation before a grant or a refund", async () => {
    const overview = {
      start: "2026-05-22",
      end: "2026-06-21",
      active_users: 1,
      open_accounts: 2,
      payments: 0,
      stars: 0,
      refunds: 0,
      sources: [],
      models: [],
      cache: {
        l1_hits: 0,
        l1_misses: 0,
        l2_hits: 0,
        process_generations: 0,
        rows_in_range: 0,
        hits_in_range: 0,
      },
      feedback: [],
      definitions: {
        active_users: text("ui.admin.active_users"),
        payments: text("ui.admin.payments"),
        cache: text("ui.admin.cache"),
        feedback: text("ui.admin.feedback"),
      },
    };
    const fetchImpl = (async () =>
      new Response(JSON.stringify(overview), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch;
    renderPage(<AdminPage isAdmin fetchImpl={fetchImpl} />);
    const grant = await screen.findByRole("button", { name: text("ui.admin.grant") });
    const refund = screen.getByRole("button", { name: text("ui.admin.refund") });
    expect(grant).toBeDisabled();
    expect(refund).toBeDisabled();
    expect(screen.queryByText("secret-name")).not.toBeInTheDocument();
  });
});
