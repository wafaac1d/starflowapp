import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SupportScreen } from "./SupportScreen";

function renderScreen() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SupportScreen />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SupportScreen", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders topbar, topic buttons, and form", () => {
    renderScreen();
    expect(screen.getByRole("heading", { name: "Поддержка" })).toBeInTheDocument();
    expect(screen.getByText("Служба поддержки и обратная связь")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Вопрос" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Оплата" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Ошибка" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Предложение" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Другое" })).toHaveAttribute("aria-pressed", "false");

    const textarea = screen.getByLabelText("Ваше сообщение");
    expect(textarea).toBeInTheDocument();

    const submitBtn = screen.getByRole("button", { name: "Отправить обращение" });
    expect(submitBtn).toBeDisabled();
  });

  it("enables button with valid message and submits ticket", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json({
        id: "123e4567-e89b-12d3-a456-426614174000",
        subject: "Оплата",
        message: "Не проходит оплата подписки в боте.",
        status: "open",
        created_at: "2026-10-29T12:00:00Z",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderScreen();
    await userEvent.click(screen.getByRole("button", { name: "Оплата" }));
    expect(screen.getByRole("button", { name: "Оплата" })).toHaveAttribute("aria-pressed", "true");

    const textarea = screen.getByLabelText("Ваше сообщение");
    await userEvent.type(textarea, "Не проходит оплата подписки в боте.");

    const submitBtn = screen.getByRole("button", { name: "Отправить обращение" });
    expect(submitBtn).toBeEnabled();

    await userEvent.click(submitBtn);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/support"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          subject: "Оплата",
          message: "Не проходит оплата подписки в боте.",
        }),
      }),
    );

    expect(await screen.findByRole("heading", { name: "Обращение отправлено" })).toBeInTheDocument();
    expect(screen.getByText(/Мы получили ваше сообщение по теме «Оплата»/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Отправить ещё одно" }));
    expect(screen.getByRole("button", { name: "Отправить обращение" })).toBeInTheDocument();
  });
});
