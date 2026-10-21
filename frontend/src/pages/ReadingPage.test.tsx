import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ReadingResponse } from "../api/client";
import { text } from "../resources";
import { ReadingPage } from "./ReadingPage";

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.toString();
  }
  return input.url;
}

function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}

function renderReading(fetchImpl: typeof fetch) {
  render(
    <QueryClientProvider client={client()}>
      <MemoryRouter>
        <ReadingPage kind="day" fetchImpl={fetchImpl} pollMs={20} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function pending(): ReadingResponse {
  return {
    status: "pending",
    title: null,
    body: null,
    greeting: null,
    user_sign: null,
    shared_facts: null,
    history_id: null,
    streak: null,
    replayed: false,
    reset_at: null,
  };
}

describe("reading page", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows loading and then the finished lowercase text", async () => {
    let polls = 0;
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (method === "POST") {
        return Response.json(pending());
      }
      polls += 1;
      if (requestUrl(input).includes("/readings/") && polls < 2) {
        return Response.json(pending());
      }
      return Response.json({
        ...pending(),
        status: "ready",
        title: "сегодня",
        body: "спокойный фон дня",
        history_id: "11111111-1111-1111-1111-111111111111",
      });
    });
    renderReading(fetchImpl);
    expect(await screen.findByText(text("ui.reading.pending"))).toBeInTheDocument();
    const body = await screen.findByText("спокойный фон дня");
    expect(body.textContent).toBe("спокойный фон дня");
    expect(body.querySelector("b")).toBeNull();
  });

  it("renders model markup as text and retries an error with a new request", async () => {
    let posts = 0;
    const keys: string[] = [];
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (method === "POST") {
        posts += 1;
        keys.push(String(new Headers(init?.headers).get("Idempotency-Key")));
        return Response.json(pending());
      }
      if (posts < 2) {
        return Response.json({ ...pending(), status: "error", body: "не удалось подготовить текст" });
      }
      return Response.json({
        ...pending(),
        status: "fallback",
        title: "сегодня",
        body: "<b>запасной</b> текст",
      });
    });
    renderReading(fetchImpl);
    expect(await screen.findByRole("alert")).toHaveTextContent("не удалось подготовить текст");
    await userEvent.click(screen.getByRole("button", { name: text("ui.common.retry") }));
    const body = await screen.findByText("<b>запасной</b> текст");
    expect(body.querySelector("b")).toBeNull();
    expect(body.textContent).toBe(body.textContent?.toLowerCase());
    expect(screen.getByText(text("ui.reading.fallback"))).toBeInTheDocument();
    expect(keys[0]).not.toBe(keys[1]);
  });
});
