import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { text } from "../resources";
import { AssistantPage } from "./AssistantPage";

describe("assistant page", () => {
  afterEach(() => {
    cleanup();
  });

  it("keeps the typed question and shows an empty history before send", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      if (init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as { text: string };
        expect(body.text).toBe("Что с Луной?");
        return Response.json({
          status: "ready",
          reply: "луна сегодня спокойная",
          remaining: 19,
          replayed: false,
          code: "ready",
        });
      }
      if (url.includes("before=")) {
        return Response.json([]);
      }
      return Response.json([]);
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <AssistantPage fetchImpl={fetchImpl} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText(text("ui.assistant.empty"))).toBeInTheDocument();
    expect(screen.getByText(text("ui.assistant.disclaimer"))).toBeInTheDocument();
    const input = screen.getByLabelText(text("ui.assistant.title"));
    expect(input).toHaveStyle({ textTransform: "none" });
    const send = screen.getByRole("button", { name: text("ui.assistant.send") });
    expect(send).toBeDisabled();
    await userEvent.type(input, "Что с Луной?");
    expect(input).toHaveValue("Что с Луной?");
    expect(send).toBeEnabled();
    await userEvent.click(send);
    expect(await screen.findByText("луна сегодня спокойная")).toBeInTheDocument();
    expect(screen.getByText(/19/)).toBeInTheDocument();
  });
});
