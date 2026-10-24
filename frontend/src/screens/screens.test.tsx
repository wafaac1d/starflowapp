import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
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

  it("keeps the birth time field open without an unknown toggle", () => {
    renderAt(<BirthScreen profile={{ ...profile(), step: "date" }} displayName="Анна" />);
    expect(screen.getByText("1 из 3")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Время рождения" })).toBeEnabled();
    expect(screen.queryByRole("switch", { name: "Не знаю время" })).not.toBeInTheDocument();
  });

  it("saves a changed birth time from the finished profile", async () => {
    const calls: { url: string; method: string; body: Record<string, unknown> }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input, init) => {
        calls.push({
          url: String(input),
          method: init?.method ?? "GET",
          body: JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>,
        });
        return Response.json({
          ...profile(),
          birth_time: "09:15",
          birth_time_unknown: false,
        });
      }),
    );
    renderAt(<BirthScreen profile={profile()} displayName="Анна" />);
    const time = screen.getByRole("textbox", { name: "Время рождения" });
    await userEvent.clear(time);
    await userEvent.type(time, "09:15");
    await userEvent.click(screen.getByRole("button", { name: "Продолжить" }));
    await waitFor(() => {
      expect(calls).toHaveLength(1);
    });
    const call = calls[0];
    expect(call).toMatchObject({
      url: "/api/v1/profile",
      method: "PATCH",
      body: { birth_date: "12.08.1995", birth_time: "09:15", birth_time_unknown: false },
    });
  });

  it("treats an empty birth time as unknown", async () => {
    const calls: { body: Record<string, unknown> }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (_input, init) => {
        calls.push({ body: JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown> });
        return Response.json({ ...profile(), birth_time: null, birth_time_unknown: true });
      }),
    );
    renderAt(<BirthScreen profile={profile()} displayName="Анна" />);
    await userEvent.clear(screen.getByRole("textbox", { name: "Время рождения" }));
    await userEvent.click(screen.getByRole("button", { name: "Продолжить" }));
    await waitFor(() => {
      expect(calls).toHaveLength(1);
    });
    expect(calls[0]?.body).toEqual({
      birth_date: "12.08.1995",
      birth_time_unknown: true,
    });
  });

  it("opens today with the forecast action", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<TodayScreen profile={profile()} />);
    expect(screen.getByRole("heading", { name: "Анна" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Открыть прогноз" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Любовь" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Совместимость" })).toBeInTheDocument();
  });

  it("keeps a topic reading behind premium", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input) => {
        calls.push(String(input));
        return Response.json({
          status: "ready",
          title: "Любовь",
          body: "Спокойный разговор важнее спешки.",
          greeting: null,
          user_sign: null,
          shared_facts: null,
          history_id: null,
          streak: null,
          replayed: false,
          reset_at: null,
        });
      }),
    );
    renderAt(<TodayScreen profile={profile()} />);
    await userEvent.click(screen.getByRole("button", { name: "Любовь" }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("Эта функция только с Premium.");
    expect(calls.some((url) => url.includes("/readings/topics"))).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Понятно" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("shows the topic text when premium is active", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async () =>
        Response.json({
          status: "ready",
          title: "Любовь",
          body: "Спокойный разговор важнее спешки.",
          greeting: null,
          user_sign: null,
          shared_facts: null,
          history_id: null,
          streak: null,
          replayed: false,
          reset_at: null,
        }),
      ),
    );
    renderAt(<TodayScreen profile={{ ...profile(), is_premium: true }} />);
    await userEvent.click(screen.getByRole("button", { name: "Любовь" }));
    expect(await screen.findByRole("alertdialog")).toHaveTextContent(
      "Спокойный разговор важнее спешки.",
    );
  });

  it("switches the forecast period", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<ForecastScreen premium={false} />);
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
    const view = renderAt(<NatalScreen />);
    expect(screen.getByRole("heading", { name: "Натальная карта" })).toBeInTheDocument();
    expect(screen.getByText("19°24′")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Сетка натальной карты" })).toBeInTheDocument();
    expect(view.container.querySelectorAll("[data-wheel='figure']").length).toBeGreaterThan(12);
    await userEvent.click(screen.getByRole("tab", { name: "Разбор" }));
    expect(screen.getByRole("tab", { name: "Разбор" })).toHaveAttribute("aria-selected", "true");
  });

  it("compares two people without saving the new one", async () => {
    const calls: { url: string; method: string; body: Record<string, unknown> }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input, init) => {
        const body =
          typeof init?.body === "string"
            ? (JSON.parse(init.body) as Record<string, unknown>)
            : {};
        calls.push({ url: String(input), method: init?.method ?? "GET", body });
        if ((init?.method ?? "GET") === "POST") {
          return Response.json({
            related_id: "new-1",
            display_name: "Михаил",
            birth_date: "1993-05-03",
            birth_time: "09:15",
            birth_time_unknown: false,
            consent: true,
          });
        }
        return Response.json([]);
      }),
    );
    renderAt(<CompatibilityScreen profile={profile()} />, "/compatibility");
    const second = screen.getByRole("region", { name: "Второй человек" });
    await userEvent.type(within(second).getByRole("textbox", { name: "Имя" }), "Михаил");
    expect(screen.queryByRole("switch", { name: "Сохранить в близкие" })).not.toBeInTheDocument();
    await userEvent.type(
      within(second).getByRole("textbox", { name: "Дата рождения" }),
      "03.05.1993",
    );
    expect(screen.getByRole("switch", { name: "Сохранить в близкие" })).toBeInTheDocument();
    await userEvent.type(within(second).getByRole("textbox", { name: "Время рождения" }), "09:15");
    expect(await screen.findByText("Телец")).toBeInTheDocument();
    expect(screen.getByText("Глубокая связь")).toBeInTheDocument();
    expect(calls.some((call) => call.method === "POST")).toBe(false);
    await userEvent.click(screen.getByRole("switch", { name: "Сохранить в близкие" }));
    await waitFor(() => {
      expect(calls.some((call) => call.method === "POST")).toBe(true);
    });
    const posted = calls.find((call) => call.method === "POST");
    expect(posted).toMatchObject({
      url: "/api/v1/related",
      body: {
        display_name: "Михаил",
        birth_date: "03.05.1993",
        birth_time: "09:15",
        birth_time_unknown: false,
        consent: true,
      },
    });
  });

  it("shows compatibility cards", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/compatibility/mikhail"]}>
          <Routes>
            <Route
              path="/compatibility/:personId"
              element={<CompatibilityScreen profile={profile()} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByRole("radio", { name: "Михаил" })).toHaveAttribute("aria-checked", "true");
    expect(await screen.findByText("Глубокая связь")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Эмоции/ }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("Эта функция только с Premium.");
  });

  it("keeps one assistant reply and the server quota", async () => {
    let sent = false;
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (_input, init) => {
        const method = init?.method ?? "GET";
        if (method === "POST") {
          sent = true;
          return Response.json({
            status: "ready",
            reply: "Один ответ.",
            remaining: 19,
            replayed: false,
            code: "ready",
          });
        }
        if (!sent) {
          return Response.json({ messages: [], remaining: 20 });
        }
        return Response.json({
          messages: [
            {
              id: "u1",
              role: "user",
              content: "Что вечером?",
              created_at: "2025-08-12T18:00:00Z",
            },
            {
              id: "a1",
              role: "assistant",
              content: "Один ответ.",
              created_at: "2025-08-12T18:00:01Z",
            },
          ],
          remaining: 19,
        });
      }),
    );
    renderAt(<ChatScreen />);
    expect(await screen.findByText("Осталось 20 вопросов")).toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox", { name: "Написать сообщение…" }), "Что вечером?");
    await userEvent.click(screen.getByRole("button", { name: "Отправить" }));
    expect(await screen.findByText("Осталось 19 вопросов")).toBeInTheDocument();
    expect(screen.getAllByText("Один ответ.")).toHaveLength(1);
    expect(screen.queryByText("Осталось 5 вопросов")).not.toBeInTheDocument();
    expect(screen.queryByText("Осталось 20 вопросов")).not.toBeInTheDocument();
  });

  it("draws the sent question and a loader before the model answers", async () => {
    let release: (response: Response) => void = () => undefined;
    const reply = new Promise<Response>((resolve) => {
      release = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (_input, init) => {
        if ((init?.method ?? "GET") === "POST") {
          return reply;
        }
        return Response.json({ messages: [], remaining: 20 });
      }),
    );
    renderAt(<ChatScreen />);
    expect(await screen.findByText("Осталось 20 вопросов")).toBeInTheDocument();
    expect(screen.getByText(/Это чат с астропомощником/)).toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox", { name: "Написать сообщение…" }), "Что вечером?");
    await userEvent.click(screen.getByRole("button", { name: "Отправить" }));
    expect(screen.getByText("Что вечером?")).toBeInTheDocument();
    expect(screen.queryByText(/Это чат с астропомощником/)).not.toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Астропомощник отвечает" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Написать сообщение…" })).toHaveValue("");
    release(
      Response.json({
        status: "ready",
        reply: "Один ответ.",
        remaining: 19,
        replayed: false,
        code: "ready",
      }),
    );
    expect(await screen.findByText("Один ответ.")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Астропомощник отвечает" })).not.toBeInTheDocument();
    expect(screen.getAllByText("Что вечером?")).toHaveLength(1);
    expect(screen.getAllByText("Один ответ.")).toHaveLength(1);
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
    expect(screen.getByRole("link", { name: "Удалить данные" })).toHaveAttribute("href", "/delete");
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
