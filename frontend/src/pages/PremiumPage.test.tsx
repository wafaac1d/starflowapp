import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { BillingResponse, ProfileResponse } from "../api/client";
import { formatText, text } from "../resources";
import { PremiumPage } from "./PremiumPage";

const profile: ProfileResponse = {
  user_id: "user",
  is_admin: false,
  is_premium: false,
  step: "done",
  display_name: "маша",
  birth_date: null,
  birth_time: null,
  birth_time_unknown: true,
  timezone: null,
  birth_place: null,
  latitude: null,
  longitude: null,
  calendar_sign: null,
};

const billing: BillingResponse = {
  premium: false,
  access_until: null,
  price_stars: 250,
  period_days: 30,
  gift_days: 30,
  trial_days: 7,
  assistant_questions: 20,
  subscription_payment_state: "pending",
  gift_payment_state: "none",
  subscription_state: "none",
  auto_renew: false,
  subscription_order_id: "order",
  subscription_invoice_link: null,
  gift_order_id: null,
  gift_invoice_link: null,
  gift_code: null,
  gift_link: null,
  trial_available: true,
  period_end: null,
};

describe("premium page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows the price and renewal before payment and waits for the server", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json(billing)),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <PremiumPage profile={profile} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(
      await screen.findByText(
        formatText("ui.premium.price_line", { price: "250", days: "30" }),
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(text("ui.premium.renew_line"))).toBeInTheDocument();
    expect(screen.getByText(text("ui.premium.gift_line"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: text("ui.premium.pay") })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(text("ui.premium.pending"));
    expect(screen.queryByText(text("ui.premium.success"))).not.toBeInTheDocument();
  });
});
