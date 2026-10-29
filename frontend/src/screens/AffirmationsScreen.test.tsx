import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AffirmationsScreen } from "./AffirmationsScreen";

function renderScreen() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AffirmationsScreen />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AffirmationsScreen", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("renders topbar, categories, and initial affirmation card", () => {
    renderScreen();
    expect(screen.getByRole("heading", { name: "Аффирмации" })).toBeInTheDocument();
    expect(screen.getByText("Мягкая настройка на день")).toBeInTheDocument();

    const forYouBtn = screen.getByRole("button", { name: "Для вас" });
    const confidenceBtn = screen.getByRole("button", { name: "Уверенность" });
    const calmBtn = screen.getByRole("button", { name: "Спокойствие" });

    expect(forYouBtn).toHaveAttribute("aria-pressed", "true");
    expect(confidenceBtn).toHaveAttribute("aria-pressed", "false");
    expect(calmBtn).toHaveAttribute("aria-pressed", "false");

    expect(
      screen.getByText(/Я доверяю себе\s+и выбираю свой ритм\./),
    ).toBeInTheDocument();

    // 3 dots
    expect(screen.getByRole("button", { name: "Аффирмация 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Аффирмация 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Аффирмация 3" })).toBeInTheDocument();

    // Action buttons
    expect(screen.getByRole("button", { name: "Сохранить аффирмацию" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Поделиться аффирмацией" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Показать другую аффирмацию" })).toBeInTheDocument();

    // Reminder switch
    expect(screen.getByRole("switch", { name: "Напоминать каждый день" })).toBeChecked();
  });

  it("switches category and updates affirmation cards", async () => {
    renderScreen();
    const confidenceBtn = screen.getByRole("button", { name: "Уверенность" });
    await userEvent.click(confidenceBtn);

    expect(confidenceBtn).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Для вас" })).toHaveAttribute("aria-pressed", "false");
    expect(
      screen.getByText(/Во мне есть всё необходимое/),
    ).toBeInTheDocument();

    const calmBtn = screen.getByRole("button", { name: "Спокойствие" });
    await userEvent.click(calmBtn);
    expect(calmBtn).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByText(/Я отпускаю спешку/),
    ).toBeInTheDocument();
  });

  it("advances to next affirmation when 'Другая аффирмация' is clicked", async () => {
    renderScreen();
    expect(screen.getByText(/Я доверяю себе/)).toBeInTheDocument();

    const nextBtn = screen.getByRole("button", { name: "Показать другую аффирмацию" });
    await userEvent.click(nextBtn);
    expect(screen.getByText(/Каждый мой шаг приближает/)).toBeInTheDocument();

    await userEvent.click(nextBtn);
    expect(screen.getByText(/Я открываюсь новому дню/)).toBeInTheDocument();

    await userEvent.click(nextBtn);
    expect(screen.getByText(/Я доверяю себе/)).toBeInTheDocument();
  });

  it("toggles saving affirmation to favorites and persists in localStorage", async () => {
    renderScreen();
    const saveBtn = screen.getByRole("button", { name: "Сохранить аффирмацию" });
    expect(saveBtn).toHaveTextContent("Сохранить");

    await userEvent.click(saveBtn);
    expect(screen.getByRole("button", { name: "Удалить из сохранённых" })).toHaveTextContent("Сохранено");
    expect(localStorage.getItem("starflow-affirmation-favorites")).toContain("for_you_1");

    await userEvent.click(screen.getByRole("button", { name: "Удалить из сохранённых" }));
    expect(screen.getByRole("button", { name: "Сохранить аффирмацию" })).toHaveTextContent("Сохранить");
    expect(localStorage.getItem("starflow-affirmation-favorites")).toBe("[]");
  });

  it("shares affirmation via navigator.share or clipboard", async () => {
    const shareMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "share", {
      value: shareMock,
      configurable: true,
    });

    renderScreen();
    const shareBtn = screen.getByRole("button", { name: "Поделиться аффирмацией" });
    await userEvent.click(shareBtn);

    expect(shareMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Аффирмация дня",
        text: expect.stringContaining("Я доверяю себе"),
      }),
    );
  });

  it("toggles daily reminder switch and saves preference", async () => {
    renderScreen();
    const toggle = screen.getByRole("switch", { name: "Напоминать каждый день" });
    expect(toggle).toBeChecked();

    await userEvent.click(toggle);
    expect(toggle).not.toBeChecked();
    expect(localStorage.getItem("starflow-affirmations-reminder")).toBe("false");

    await userEvent.click(toggle);
    expect(toggle).toBeChecked();
    expect(localStorage.getItem("starflow-affirmations-reminder")).toBe("true");
  });

  it("swipes horizontally to switch cards", () => {
    renderScreen();
    const cardRegion = screen.getByRole("region", { name: "Карточка аффирмации" });
    expect(screen.getByText(/Я доверяю себе/)).toBeInTheDocument();

    // Swipe left (next)
    fireEvent.touchStart(cardRegion, { touches: [{ clientX: 200, clientY: 100 }] });
    fireEvent.touchEnd(cardRegion, { changedTouches: [{ clientX: 100, clientY: 100 }] });
    expect(screen.getByText(/Каждый мой шаг приближает/)).toBeInTheDocument();

    // Swipe right (prev)
    fireEvent.touchStart(cardRegion, { touches: [{ clientX: 100, clientY: 100 }] });
    fireEvent.touchEnd(cardRegion, { changedTouches: [{ clientX: 200, clientY: 100 }] });
    expect(screen.getByText(/Я доверяю себе/)).toBeInTheDocument();
  });
});
