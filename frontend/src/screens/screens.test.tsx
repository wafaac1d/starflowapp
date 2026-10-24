import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { ProfileResponse } from "../api/client";
import { BirthScreen } from "./BirthScreen";
import { CalendarScreen } from "./CalendarScreen";
import { ChatScreen } from "./ChatScreen";
import { CompatibilityScreen } from "./CompatibilityScreen";
import { ForecastScreen } from "./ForecastScreen";
import { NatalScreen } from "./NatalScreen";
import { PeopleScreen } from "./PeopleScreen";
import { PremiumScreen } from "./PremiumScreen";
import { ProfileScreen } from "./ProfileScreen";
import { SettingsScreen } from "./SettingsScreen";
import { TodayScreen } from "./TodayScreen";
import { WelcomeScreen } from "./WelcomeScreen";

function profile(): ProfileResponse {
  return {
    user_id: "00000000-0000-0000-0000-000000000001",
    is_admin: false,
    is_premium: false,
    step: "done",
    display_name: "Анна",
    birth_date: "12.08.1995",
    birth_time: "14:30",
    birth_time_unknown: false,
    timezone: "Europe/Moscow",
    birth_place: null,
    latitude: null,
    longitude: null,
    calendar_sign: "Лев",
  };
}

function renderAt(ui: ReactNode, path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("screens", () => {
  it("shows the welcome copy", async () => {
    renderAt(<WelcomeScreen />);
    expect(screen.getByRole("heading", { name: /Ваш ритм/ })).toBeInTheDocument();
    expect(screen.getByText(/персональный астропомощник/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Начать" })).toBeInTheDocument();
  });

  it("disables the birth time when the toggle is on", async () => {
    renderAt(<BirthScreen profile={{ ...profile(), step: "date" }} displayName="Анна" />);
    expect(screen.getByText("1 из 3")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Время рождения" })).toBeEnabled();
    await userEvent.click(screen.getByRole("switch", { name: "Не знаю время" }));
    expect(screen.getByRole("textbox", { name: "Время рождения" })).toBeDisabled();
  });

  it("opens today with the forecast action", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<TodayScreen profile={profile()} />);
    expect(screen.getByRole("heading", { name: "Анна" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Открыть прогноз" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Любовь" })).toBeInTheDocument();
  });

  it("switches the forecast period", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<ForecastScreen />);
    expect(await screen.findByText("Гармония и откровенность")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Неделя" }));
    expect(screen.getByRole("tab", { name: "Неделя" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: "Поделиться" })).toBeInTheDocument();
  });

  it("shows the lunar day card", async () => {
    renderAt(<CalendarScreen />, "/calendar?day=2025-08-12");
    expect(await screen.findByText("Растущая Луна, 1 фаза")).toBeInTheDocument();
    expect(await screen.findByText("Хорошее время для планов, обучения и общения.")).toBeInTheDocument();
  });

  it("shows the natal rows", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<NatalScreen />);
    expect(screen.getByRole("heading", { name: "Натальная карта" })).toBeInTheDocument();
    expect(screen.getByText("19°24′")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Разбор" }));
    expect(screen.getByRole("tab", { name: "Разбор" })).toHaveAttribute("aria-selected", "true");
  });

  it("shows compatibility cards", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<CompatibilityScreen profile={profile()} />, "/compatibility/mikhail");
    expect(screen.getByText("Михаил")).toBeInTheDocument();
    expect(await screen.findByText("Глубокая связь")).toBeInTheDocument();
  });

  it("shows the assistant quota", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<ChatScreen />);
    expect(await screen.findByText("Осталось 5 вопросов")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Написать сообщение…" })).toBeInTheDocument();
  });

  it("lists people from the api", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(
          JSON.stringify([
            { related_id: "mama", display_name: "Мама", birth_date: "14.03.1968" },
            { related_id: "daniil", display_name: "Даниил", birth_date: "22.11.1988" },
            { related_id: "sergey", display_name: "Сергей", birth_date: "17.06.1992" },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    renderAt(<PeopleScreen />);
    expect(await screen.findByRole("button", { name: /Мама/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Добавить человека" })).toBeInTheDocument();
  });

  it("links the subscription from the profile", () => {
    renderAt(<ProfileScreen profile={profile()} />);
    expect(screen.getByRole("heading", { name: "Анна" })).toBeInTheDocument();
    expect(screen.getByText("Лев · 12.08.1995")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Моя подписка" })).toHaveAttribute("href", "/premium");
  });

  it("toggles a settings switch", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<SettingsScreen />);
    const master = screen.getByRole("switch", { name: "Уведомления" });
    expect(master).toBeChecked();
    await userEvent.click(master);
    expect(master).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "Тёмная" })).toBeInTheDocument();
  });

  it("shows the premium offer", () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<PremiumScreen />);
    expect(screen.getByRole("heading", { name: "Больше о себе" })).toBeInTheDocument();
    expect(screen.getByText(/250 звёзд \/ 30 дней/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Подключить" })).toBeInTheDocument();
  });
});
