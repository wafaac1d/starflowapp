import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ChartResponse, SkyResponse } from "../api/client";
import { text } from "../resources";
import { ChartPage } from "./ChartPage";

const sky: SkyResponse = {
  sun_sign: "козерог",
  moon_sign: "рак",
  phase_name: "растущий серп",
  bodies: [],
};

function unknownChart(): ChartResponse {
  return {
    sun_sign: "козерог",
    sun_sign_source: "calendar",
    moon_sign: null,
    ascendant_sign: null,
    houses: null,
    planets: [],
    aspects: [],
    transits: [],
    lunar_day: null,
    phase_name: null,
    limitations: ["time_unknown", "place_missing"],
    natal_access: "premium_required",
  };
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  return input.url;
}

function renderChart(chart: ChartResponse) {
  const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
    const url = requestUrl(input);
    if (url.includes("/sky")) {
      return Response.json(sky);
    }
    return Response.json(chart);
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ChartPage fetchImpl={fetchImpl} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("chart page", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows unknown birth data and the paywall instead of an empty error", async () => {
    renderChart(unknownChart());
    expect(await screen.findByText("козерог")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: text("ui.chart.title") })).toBeInTheDocument();
    expect(screen.getByText(text("ui.chart.time_unknown"))).toBeInTheDocument();
    expect(screen.getByText(text("ui.chart.place_missing"))).toBeInTheDocument();
    expect(screen.getByText(text("ui.chart.moon_unknown"))).toBeInTheDocument();
    expect(screen.getByText(text("ui.chart.asc_unknown"))).toBeInTheDocument();
    expect(screen.getByText(text("ui.chart.houses_unknown"))).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: text("ui.paywall.title") })).toBeInTheDocument();
    expect(screen.getByText(text("ui.paywall.lead"))).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps the calendar sign visible when only the paywall applies", async () => {
    renderChart({ ...unknownChart(), limitations: [], sun_sign_source: "ephemeris" });
    expect(await screen.findByText("козерог")).toBeInTheDocument();
    expect(screen.getByText(text("ui.chart.ephemeris_source"))).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: text("ui.paywall.title") })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
