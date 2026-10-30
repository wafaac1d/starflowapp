import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { ProfileResponse } from "../api/client";
import { queryKeys } from "../api/keys";
import { applyTheme, readThemeChoice } from "../theme";
import { BirthScreen } from "./BirthScreen";
import { CalendarScreen } from "./CalendarScreen";
import { ChatScreen } from "./ChatScreen";
import { CompatibilityScreen } from "./CompatibilityScreen";
import { ForecastScreen } from "./ForecastScreen";
import { NatalScreen } from "./NatalScreen";
import { FavoritesScreen, SavedFavoriteScreen } from "./FavoritesScreen";
import { FavorableDateScreen } from "./FavorableDateScreen";
import { AffirmationsScreen } from "./PracticeScreens";
import { PeopleScreen } from "./PeopleScreen";
import { PremiumScreen } from "./PremiumScreen";
import { ProfileScreen } from "./ProfileScreen";
import { RetroScreen } from "./RetroScreen";
import { SettingsScreen } from "./SettingsScreen";
import { TodayScreen } from "./TodayScreen";
import styles from "./screens.module.css";
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
    star_balance: 0,
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

  it("inserts dots and a colon while the birth date and time are typed", async () => {
    renderAt(<BirthScreen profile={{ ...profile(), step: "date", birth_date: null, birth_time: null }} displayName="Анна" />);
    const date = screen.getByRole("textbox", { name: "Дата рождения" });
    const time = screen.getByRole("textbox", { name: "Время рождения" });
    await userEvent.type(date, "12081995");
    await userEvent.type(time, "1430");
    expect(date).toHaveValue("12.08.1995");
    expect(time).toHaveValue("14:30");
  });

  it("keeps the birth time field open without an unknown toggle", () => {
    renderAt(<BirthScreen profile={{ ...profile(), step: "date" }} displayName="Анна" />);
    expect(screen.getByText("1 из 3")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Время рождения" })).toBeEnabled();
    expect(screen.queryByRole("switch", { name: "Не знаю время" })).not.toBeInTheDocument();
    expect(
      screen.getByText("Можно оставить пустым, если не знаете время рождения"),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Город рождения" })).toBeInTheDocument();
    expect(
      screen.getByText("Можно оставить пустым, если не хотите указывать город"),
    ).toBeInTheDocument();
  });

  it("finishes registration when the birth time field stays untouched", async () => {
    const calls: Record<string, unknown>[] = [];
    let step = "welcome";
    const draft: ProfileResponse = {
      ...profile(),
      step: "welcome",
      display_name: null,
      birth_date: null,
      birth_time: null,
      birth_time_unknown: false,
      timezone: null,
      calendar_sign: null,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (_input, init) => {
        const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
        calls.push(body);
        if (step === "welcome") {
          step = "name";
        } else if (step === "name") {
          if (typeof body.display_name !== "string") {
            return Response.json({ message: "name" }, { status: 422 });
          }
          step = "date";
        } else if (step === "date") {
          step = "time";
        } else if (step === "time" && body.birth_time_unknown === true) {
          step = "done";
        }
        return Response.json({
          ...draft,
          step,
          display_name: step === "welcome" || step === "name" ? null : "Анна",
          birth_date:
            step === "welcome" || step === "name" || step === "date" ? null : "12.08.1995",
          birth_time: null,
          birth_time_unknown: step === "done",
          timezone: step === "done" ? "Europe/Moscow" : null,
          calendar_sign: step === "done" ? "Лев" : null,
        });
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/onboarding/birth"]}>
          <Routes>
            <Route
              path="/onboarding/birth"
              element={<BirthScreen profile={draft} displayName="Анна" />}
            />
            <Route path="/" element={<h1>Сегодня</h1>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.type(screen.getByRole("textbox", { name: "Дата рождения" }), "12.08.1995");
    await userEvent.click(screen.getByRole("button", { name: "Продолжить" }));
    expect(await screen.findByRole("heading", { name: "Сегодня" })).toBeInTheDocument();
    expect(calls.some((body) => body.birth_time_unknown === true && body.birth_time === undefined)).toBe(
      true,
    );
    expect(screen.queryByRole("textbox", { name: "Время рождения" })).not.toBeInTheDocument();
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
    expect(screen.getByRole("heading", { name: "Ваши астропрактики" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: (value) => value.startsWith("Натальная карта") })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: (value) => value.startsWith("Совместимость") })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: (value) => value.startsWith("Ретроградные планеты") })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: (value) => value.startsWith("Аффирмации") })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: (value) => value.startsWith("Благоприятная дата") })).toBeInTheDocument();
    expect(await screen.findByText("Не удалось связаться со звёздами")).toBeInTheDocument();
    expect(screen.queryByText("День для ясных решений")).not.toBeInTheDocument();
  });

  it("shows unlim beside the balance while premium is active", () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<TodayScreen profile={{ ...profile(), is_premium: true, star_balance: 15 }} />);
    const balance = screen.getByRole("button", { name: "Баланс unlim/15" });
    const rest = styles.balanceRest;
    if (rest === undefined) {
      throw new Error("balance rest style is missing");
    }
    expect(within(balance).getByText("unlim")).toBeInTheDocument();
    expect(within(balance).getByText("/15")).toHaveClass(rest);
  });

  it("opens a top-up from the balance", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<TodayScreen profile={{ ...profile(), star_balance: 15 }} />);
    await userEvent.click(screen.getByRole("button", { name: "Баланс 15" }));
    const dialog = screen.getByRole("dialog", { name: "Пополнение" });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: (value) => value === "10" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(dialog).getByRole("button", { name: "20" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "50" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "100" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: (value) => value.startsWith("Оплатить") })).toBeEnabled();
    expect(within(dialog).getByRole("textbox", { name: "Код" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Активировать" })).toBeDisabled();
    expect(within(dialog).getByRole("link", { name: (value) => value === "Premium" })).toHaveAttribute(
      "href",
      "/premium",
    );
    expect(within(dialog).getByRole("link", { name: "t.me/PremiumBot" })).toHaveAttribute(
      "href",
      "https://t.me/PremiumBot",
    );
    expect(dialog).toHaveTextContent("Можно подключить");
    await userEvent.click(within(dialog).getByRole("button", { name: "Закрыть" }));
    expect(screen.queryByRole("dialog", { name: "Пополнение" })).not.toBeInTheDocument();
  });

  it("shows the day title only after the reading is ready", async () => {
    let release: (response: Response) => void = () => undefined;
    const gate = new Promise<Response>((resolve) => {
      release = resolve;
    });
    vi.stubGlobal("fetch", vi.fn<typeof fetch>(async () => gate));
    renderAt(<TodayScreen profile={profile()} />);
    expect(screen.queryByText("День для ясных решений")).not.toBeInTheDocument();
    expect(screen.queryByText("Не удалось связаться со звёздами")).not.toBeInTheDocument();
    release(
      Response.json({
        status: "ready",
        title: "Ясный день",
        body: "Текст дня.",
        greeting: null,
        user_sign: null,
        shared_facts: null,
        history_id: null,
        streak: null,
        replayed: false,
        reset_at: null,
      }),
    );
    expect(await screen.findByText("Ясный день")).toBeInTheDocument();
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

  it("keeps the topic dialog on a loader until the reading is ready", async () => {
    let release: (response: Response) => void = () => undefined;
    const gate = new Promise<Response>((resolve) => {
      release = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input) => {
        if (String(input).includes("/readings/topics")) {
          return gate;
        }
        return Response.json({
          status: "ready",
          title: "День",
          body: "Текст дня.",
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
    renderAt(<TodayScreen profile={{ ...profile(), is_premium: true }} />);
    await userEvent.click(screen.getByRole("button", { name: "Любовь" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByText("Не удалось связаться со звёздами")).not.toBeInTheDocument();
    release(
      Response.json({
        status: "ready",
        title: "Любовь",
        body: "Текст темы.",
        greeting: null,
        user_sign: null,
        shared_facts: null,
        history_id: null,
        streak: null,
        replayed: false,
        reset_at: null,
      }),
    );
    expect(await screen.findByText("Текст темы.")).toBeInTheDocument();
    expect(screen.getByRole("alertdialog")).toHaveAttribute("aria-busy", "false");
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
    expect(await screen.findByText("Гармония и искренний диалог...")).toBeInTheDocument();
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
    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось связаться со звёздами");
    expect(screen.queryByText("19°24′")).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Сетка натальной карты" })).not.toBeInTheDocument();
    expect(view.container.querySelectorAll("[data-wheel='figure']")).toHaveLength(0);
    await userEvent.click(screen.getByRole("tab", { name: "Разбор" }));
    expect(screen.getByRole("tab", { name: "Разбор" })).toHaveAttribute("aria-selected", "true");
  });

  it("asks for 40 stars before showing a natal chart without premium", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input, init) => {
        if (String(input).includes("/stars/spends") && init?.method === "POST") {
          return Response.json({ balance: 0 }, { status: 402 });
        }
        return Response.json({
          sun_sign: "лев",
          sun_sign_source: "ephemeris",
          moon_sign: "рыбы",
          ascendant_sign: "скорпион",
          houses: ["скорпион"],
          house_cusps: [210],
          planets: [{ id: "sun", name: "солнце", sign: "лев", degree: 19.4, longitude: 139.4 }],
          aspects: [],
          transits: [],
          lunar_day: null,
          phase_name: null,
          limitations: [],
          natal_access: "stars_required",
          sections: [],
        });
      }),
    );
    renderAt(<NatalScreen />);
    expect(await screen.findByRole("button", { name: "Открыть за 40" })).toBeInTheDocument();
    expect(screen.queryByText("19°24′")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Открыть за 40" }));
    expect(await screen.findByRole("dialog", { name: "Пополнение" })).toBeInTheDocument();
  });

  it("waits for a long natal reading instead of the short section", async () => {
    let release: (response: Response) => void = () => undefined;
    const gate = new Promise<Response>((resolve) => {
      release = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input) => {
        if (String(input).includes("/readings/natal")) {
          return gate;
        }
        return Response.json({
          sun_sign: "лев",
          sun_sign_source: "ephemeris",
          moon_sign: "рыбы",
          ascendant_sign: "скорпион",
          houses: ["скорпион"],
          house_cusps: [210],
          planets: [],
          aspects: [],
          transits: [],
          lunar_day: null,
          phase_name: null,
          limitations: [],
          natal_access: "allowed",
          sections: [
            {
              id: "sun",
              title: "Солнце",
              body: "Короткая подпись, которую подробный разбор заменяет.",
            },
          ],
        });
      }),
    );
    renderAt(<NatalScreen />);
    await userEvent.click(await screen.findByRole("tab", { name: "Разбор" }));
    expect(await screen.findByRole("region", { name: "Разбор" })).toHaveAttribute("aria-busy", "true");
    expect(
      screen.queryByText("Короткая подпись, которую подробный разбор заменяет."),
    ).not.toBeInTheDocument();
    release(
      Response.json({
        status: "ready",
        title: "Карта Льва",
        body: "Солнце во Льве задаёт долгий разбор из нескольких предложений про стиль, а не прогноз на один день.",
        greeting: null,
        user_sign: null,
        shared_facts: null,
        history_id: null,
        streak: null,
        replayed: false,
        reset_at: null,
      }),
    );
    expect(await screen.findByText(/долгий разбор/)).toBeInTheDocument();
    expect(
      screen.queryByText("Короткая подпись, которую подробный разбор заменяет."),
    ).not.toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: (value) => value.startsWith("Проверить") })).toBeEnabled();
    expect(screen.queryByText("Глубокая связь")).not.toBeInTheDocument();
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
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input) => {
        if (String(input).includes("/stars/spends")) {
          return Response.json({ balance: 0, allowed: true, charged: true, price: 40 });
        }
        throw new Error("offline");
      }),
    );
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
    expect(screen.queryByText("Теплота и взаимная забота...")).not.toBeInTheDocument();
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query.includes("reduce"),
      media: query,
      addEventListener() {},
      removeEventListener() {},
    }));
    await userEvent.click(screen.getByRole("button", { name: (value) => value.startsWith("Проверить") }));
    expect(await screen.findByText("Теплота и взаимная забота...")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Эмоции/ }));
    expect(await screen.findByRole("alertdialog")).toHaveTextContent(
      "Не удалось связаться со звёздами",
    );
  });

  it("asks the pair focus instead of a daily topic", async () => {
    const calls: string[] = [];
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query.includes("reduce"),
      media: query,
      addEventListener() {},
      removeEventListener() {},
    }));
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input) => {
        const url = String(input);
        calls.push(url);
        if (url.includes("/readings/synastry")) {
          return Response.json({
            status: "ready",
            title: "Эмоции пары",
            body: "Этим двоим ближе тихий разговор, чем общий прогноз на день.",
            greeting: null,
            user_sign: null,
            shared_facts: null,
            history_id: null,
            streak: null,
            replayed: false,
            reset_at: null,
          });
        }
        return Response.json([]);
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/compatibility/mikhail"]}>
          <Routes>
            <Route
              path="/compatibility/:personId"
              element={<CompatibilityScreen profile={{ ...profile(), is_premium: true }} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: (value) => value.startsWith("Проверить") }));
    await userEvent.click(await screen.findByRole("button", { name: /Эмоции/ }));
    expect(
      await screen.findByText("Этим двоим ближе тихий разговор, чем общий прогноз на день."),
    ).toBeInTheDocument();
    const reading = calls.find((url) => url.includes("/readings/synastry"));
    if (typeof reading !== "string") {
      expect(reading).toBe("synastry request");
      return;
    }
    const params = new URL(reading, "http://starflow.local").searchParams;
    expect(params.get("topic")).toBe("emotions");
    expect(params.get("left_sign")).toBe("лев");
    expect(params.get("right_sign")).toBe("телец");
    expect(calls.some((url) => url.includes("/readings/topics"))).toBe(false);
  });

  it("holds the star link for two seconds", async () => {
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      media: "",
      addEventListener() {},
      removeEventListener() {},
    }));
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input) => {
        if (String(input).includes("/stars/spends")) {
          return Response.json({ balance: 0, allowed: true, charged: true, price: 40 });
        }
        throw new Error("offline");
      }),
    );
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
    try {
      fireEvent.click(screen.getByRole("button", { name: (value) => value.startsWith("Проверить") }));
      expect(screen.getByRole("status")).toHaveTextContent("Связь со звёздами");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1999);
      });
      expect(screen.queryByText("Теплота и взаимная забота...")).not.toBeInTheDocument();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      expect(screen.getByText("Теплота и взаимная забота...")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
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
    renderAt(<ChatScreen premium />);
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
    renderAt(<ChatScreen premium />);
    expect(await screen.findByText("Осталось 20 вопросов")).toBeInTheDocument();
    expect(screen.getByText(/Это чат с астропомощником/)).toBeInTheDocument();
    expect(screen.queryByText(/можно с Premium/)).not.toBeInTheDocument();
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

  it("lets a question through without premium and shows its price", async () => {
    const fetchMock = vi.fn<typeof fetch>(async (_input, init) => {
      if ((init?.method ?? "GET") === "POST") {
        return Response.json({ status: "premium", reply: null, remaining: null, replayed: false, code: "premium_required" });
      }
      return Response.json({
        messages: [
          {
            id: "a1",
            role: "assistant",
            content: "Старый ответ.",
            created_at: "2025-08-12T18:00:01Z",
          },
        ],
        remaining: null,
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    renderAt(<ChatScreen premium={false} balance={20} />);
    expect(await screen.findByText("Старый ответ.")).toBeInTheDocument();
    expect(
      screen.getByText(
        (_, node) =>
          node?.tagName === "P" &&
          node.textContent?.replace(/\s+/g, " ").trim() === "20 звёзд за вопрос",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Писать и отправлять сообщения можно с Premium.")).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Написать сообщение…" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Отправить" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Отправить" }));
    expect(fetchMock.mock.calls.some((call) => (call[1]?.method ?? "GET") === "POST")).toBe(false);
  });

  it("drops the star balance as soon as a question is sent", async () => {
    let release: (response: Response) => void = () => undefined;
    const gate = new Promise<Response>((resolve) => {
      release = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (_input, init) => {
        if ((init?.method ?? "GET") === "POST") {
          return gate;
        }
        return Response.json({ messages: [], remaining: null });
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(queryKeys.session, { ...profile(), star_balance: 40 });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ChatScreen premium={false} balance={40} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.type(
      await screen.findByRole("textbox", { name: "Написать сообщение…" }),
      "Что вечером?",
    );
    await userEvent.click(screen.getByRole("button", { name: "Отправить" }));
    await waitFor(() => {
      expect(client.getQueryData<ProfileResponse>(queryKeys.session)?.star_balance).toBe(20);
    });
    release(
      Response.json({
        status: "ready",
        reply: "Тихий вечер.",
        remaining: null,
        replayed: false,
        code: "ready",
      }),
    );
    expect(await screen.findByText("Тихий вечер.")).toBeInTheDocument();
  });

  it("closes the chat field when the star balance cannot pay for a question", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async () => Response.json({ messages: [], remaining: null })),
    );
    renderAt(<ChatScreen premium={false} balance={0} />);
    const field = await screen.findByRole("textbox", { name: "Недостаточно звёзд" });
    expect(field).toBeDisabled();
    expect(screen.getByRole("button", { name: "Отправить" })).toBeDisabled();
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
    await userEvent.click(screen.getByRole("button", { name: "Добавить человека" }));
    expect(screen.getByRole("textbox", { name: "Имя" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Дата рождения" })).toBeInTheDocument();
  });

  it("shows shimmering row silhouettes while people load", () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>(() => new Promise(() => undefined)));
    const view = renderAt(<PeopleScreen />);
    expect(view.container.querySelectorAll("div[aria-hidden='true'] > span")).toHaveLength(3);
  });

  it("links the subscription from the profile", () => {
    renderAt(<ProfileScreen profile={profile()} />);
    expect(screen.getByRole("heading", { name: "Анна" })).toBeInTheDocument();
    expect(screen.getByText("Лев · 12.08.1995")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Избранное" })).toHaveAttribute("href", "/favorites");
    expect(screen.queryByRole("link", { name: "История" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Моя подписка" })).toHaveAttribute("href", "/premium");
    expect(screen.getByRole("link", { name: "Поддержка" })).toHaveAttribute("href", "/support");
    expect(screen.getByRole("button", { name: "Редактировать профиль" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Добавить близкого" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Удалить данные" })).toHaveAttribute("href", "/delete");
    expect(screen.queryByRole("link", { name: "Админ" })).not.toBeInTheDocument();
  });

  it("lists saved readings on the favorites screen", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(
          JSON.stringify([
            { history_id: "11111111-1111-1111-1111-111111111111", title: "День для ясных решений" },
            { history_id: "22222222-2222-2222-2222-222222222222", title: "Неделя спокойных дел" },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    renderAt(<FavoritesScreen />);
    expect(screen.getByRole("heading", { name: "Избранное" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "День для ясных решений" })).toHaveAttribute(
      "href",
      "/favorites/11111111-1111-1111-1111-111111111111",
    );
    expect(screen.getByRole("link", { name: "Неделя спокойных дел" })).toBeInTheDocument();
    expect(screen.queryByText("В избранном пока пусто")).not.toBeInTheDocument();
  });

  it("opens a saved forecast from the favorites list", async () => {
    const historyId = "11111111-1111-1111-1111-111111111111";
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input) => {
        const url = String(input);
        if (url.includes(`/favorites/${historyId}`)) {
          return Response.json({
            history_id: historyId,
            title: "День для ясных решений",
            body: "Текст сохранённого дня.",
          });
        }
        return Response.json([{ history_id: historyId, title: "День для ясных решений" }]);
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/favorites"]}>
          <Routes>
            <Route path="/favorites" element={<FavoritesScreen />} />
            <Route path="/favorites/:historyId" element={<SavedFavoriteScreen />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.click(await screen.findByRole("link", { name: "День для ясных решений" }));
    expect(await screen.findByRole("heading", { name: "День для ясных решений" })).toBeInTheDocument();
    expect(screen.getByText("Текст сохранённого дня.")).toBeInTheDocument();
  });

  it("keeps save closed when the forecast is already stored", async () => {
    const historyId = "11111111-1111-1111-1111-111111111111";
    const reading = {
      status: "ready",
      title: "День",
      body: "Текст дня.",
      greeting: null,
      user_sign: null,
      shared_facts: null,
      history_id: historyId,
      streak: null,
      replayed: true,
      reset_at: null,
    };
    const stored = [{ history_id: historyId, title: "День" }];
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input, init) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url.includes("/favorites") && method === "POST") {
          return Response.json({ favorite_id: historyId, target_id: historyId, replayed: false });
        }
        if (url.includes("/favorites")) {
          return Response.json(stored);
        }
        if (url.includes("/readings/")) {
          return Response.json(reading);
        }
        return Response.json([]);
      }),
    );
    const first = renderAt(<ForecastScreen premium={false} />);
    expect(await screen.findByRole("button", { name: "Сохранено" })).toBeDisabled();
    first.unmount();
    renderAt(<ForecastScreen premium={false} />);
    expect(await screen.findByRole("button", { name: "Сохранено" })).toBeDisabled();
  });

  it("closes save after the forecast is stored and keeps it closed", async () => {
    const historyId = "11111111-1111-1111-1111-111111111111";
    const reading = {
      status: "ready",
      title: "День",
      body: "Текст дня.",
      greeting: null,
      user_sign: null,
      shared_facts: null,
      history_id: historyId,
      streak: null,
      replayed: false,
      reset_at: null,
    };
    const stored: { history_id: string; title: string }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input, init) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url.includes("/favorites") && method === "POST") {
          stored.push({ history_id: historyId, title: "День" });
          return Response.json({ favorite_id: historyId, target_id: historyId, replayed: false });
        }
        if (url.includes("/favorites")) {
          return Response.json(stored);
        }
        if (url.includes("/readings/")) {
          return Response.json(reading);
        }
        return Response.json([]);
      }),
    );
    const first = renderAt(<ForecastScreen premium={false} />);
    await userEvent.click(await screen.findByRole("button", { name: "Сохранить" }));
    expect(await screen.findByRole("button", { name: "Сохранено" })).toBeDisabled();
    first.unmount();
    renderAt(<ForecastScreen premium={false} />);
    expect(await screen.findByRole("button", { name: "Сохранено" })).toBeDisabled();
  });

  it("shows an empty favorites screen", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(Response.json([])));
    renderAt(<FavoritesScreen />);
    expect(await screen.findByText("В избранном пока пусто")).toBeInTheDocument();
  });

  it("opens the admin page from the profile when the session is an admin", () => {
    renderAt(<ProfileScreen profile={{ ...profile(), is_admin: true }} />);
    expect(screen.getByRole("link", { name: "Админ" })).toHaveAttribute("href", "/admin");
  });

  it("toggles a settings switch", async () => {
    localStorage.removeItem("starflow-theme");
    const previous = window.Telegram;
    try {
      window.Telegram = { WebApp: { colorScheme: "dark" } };
      applyTheme(readThemeChoice());
      expect(document.documentElement.dataset.themeChoice).toBe("telegram");
      expect(document.documentElement.dataset.theme).toBe("dark");
      window.Telegram = { WebApp: { colorScheme: "light" } };
      applyTheme(readThemeChoice());
      expect(document.documentElement.dataset.theme).toBe("light");
    } finally {
      if (previous === undefined) delete window.Telegram;
      else window.Telegram = previous;
    }
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<SettingsScreen />);
    const master = screen.getByRole("switch", { name: "Уведомления" });
    expect(master).toBeChecked();
    await userEvent.click(master);
    expect(master).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "Авто" })).toBeChecked();
    await userEvent.click(screen.getByRole("radio", { name: "Светлая" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(screen.getByRole("radio", { name: "Светлая" })).toBeChecked();
    await userEvent.click(screen.getByRole("radio", { name: "Тёмная" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("shows the premium offer", () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    renderAt(<PremiumScreen />);
    expect(screen.getByRole("heading", { name: "Больше о себе" })).toBeInTheDocument();
    expect(screen.getByText(/250 звёзд \/ 30 дней/)).toBeInTheDocument();
    expect(screen.getByText("Аффирмации")).toBeInTheDocument();
    expect(screen.getByText("Благоприятная дата")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Подключить" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Списать 250 с баланса" })).toBeInTheDocument();
    expect(screen.getByText("Разовое списание с баланса, без автопродления.")).toBeInTheDocument();
  });

  it("shows the remaining days when premium is already active", async () => {
    const until = new Date(Date.now() + 10 * 86_400_000).toISOString();
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async () =>
        Response.json({
          premium: true,
          access_until: until,
          price_stars: 250,
          period_days: 30,
          gift_days: 30,
          trial_days: 7,
          assistant_questions: 40,
          subscription_payment_state: "none",
          gift_payment_state: "none",
          subscription_state: "active",
          auto_renew: true,
          subscription_order_id: null,
          subscription_invoice_link: null,
          gift_order_id: null,
          gift_invoice_link: null,
          gift_code: null,
          gift_link: null,
          trial_available: false,
          period_end: until,
        }),
      ),
    );
    renderAt(<PremiumScreen subscribed />);
    expect(await screen.findByText(/Осталось 10 дней/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Моя подписка" })).toBeInTheDocument();
    expect(screen.getByText("Персональные прогнозы")).toBeInTheDocument();
    expect(screen.getByText("Аффирмации")).toBeInTheDocument();
    expect(screen.getByText("Благоприятная дата")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Подключить" })).not.toBeInTheDocument();
  });

  it("opens retrograde planets from today and reminds about the period", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-18T12:00:00"));
    const calls: { url: string; method: string; body: Record<string, unknown> }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        const body =
          typeof init?.body === "string"
            ? (JSON.parse(init.body) as Record<string, unknown>)
            : {};
        calls.push({ url, method, body });
        if (url.includes("/retro")) {
          return Response.json([
            { planet: "меркурий", start: "2026-11-09", end: "2026-11-29" },
            { planet: "сатурн", start: "2026-07-26", end: "2026-12-10" },
            { planet: "венера", start: "2026-12-05", end: "2026-12-20" },
          ]);
        }
        if (url.includes("/notifications")) {
          if (method === "PUT") {
            return Response.json(body);
          }
          return Response.json({
            local_time: "08:30",
            timezone: "Europe/Moscow",
            day: true,
            moon: false,
            retro: false,
          });
        }
        return Response.json({
          title: "День для ясных решений",
          body: "Короткий день.",
          source: "model",
        });
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    try {
      render(
        <QueryClientProvider client={client}>
          <MemoryRouter initialEntries={["/"]}>
            <Routes>
              <Route path="/" element={<TodayScreen profile={profile()} />} />
              <Route path="/retro" element={<RetroScreen />} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>,
      );
      expect(await screen.findByText("2 периода")).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: (value) => value.startsWith("Ретроградные планеты") }));
      expect(await screen.findByRole("heading", { name: "Ретроградные планеты" })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Меркурий" })).toBeInTheDocument();
      expect(screen.getByText("9–29 ноября")).toBeInTheDocument();
      expect(screen.getAllByText("Ретроградный")).toHaveLength(2);
      await userEvent.click(screen.getByRole("tab", { name: "Скоро" }));
      expect(screen.getByRole("heading", { name: "Венера" })).toBeInTheDocument();
      expect(screen.queryByRole("heading", { name: "Меркурий" })).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole("tab", { name: "Все" }));
      expect(screen.getByRole("heading", { name: "Сатурн" })).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Напомнить о периоде" }));
      await waitFor(() => {
        expect(calls.some((call) => call.url.includes("/notifications") && call.method === "PUT")).toBe(true);
      });
      const saved = calls.find((call) => call.method === "PUT");
      expect(saved?.body).toMatchObject({ retro: true, local_time: "08:30" });
      expect(screen.getByRole("button", { name: "Напоминание включено" })).toBeDisabled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("opens affirmations and a favorable date from today", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new Error("offline")));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<TodayScreen profile={profile()} />} />
            <Route path="/affirmations" element={<AffirmationsScreen />} />
            <Route path="/favorable" element={<FavorableDateScreen />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: (value) => value.startsWith("Аффирмации") }));
    expect(await screen.findByRole("heading", { name: "Аффирмации" })).toBeInTheDocument();
    expect(screen.getByText("Мягкая настройка на день")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Назад" }));
    await userEvent.click(screen.getByRole("button", { name: (value) => value.startsWith("Благоприятная дата") }));
    expect(await screen.findByRole("heading", { name: "Благоприятная дата" })).toBeInTheDocument();
    expect(screen.getByText("Для какого события ищем день?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Встреча" })).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(screen.getByRole("button", { name: "Встреча" }));
    expect(screen.getByRole("button", { name: "Встреча" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows a favorable day from the model and saves it to the calendar", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2025-08-12T12:00:00"));
    try {
      const createObjectURL = vi.fn(() => "blob:favorable");
      Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
      Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: () => undefined });
      vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
      let opened = false;
      vi.stubGlobal(
        "fetch",
        vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
          const url = String(input);
          if (url.includes("/stars/spends")) {
            opened = true;
            return Response.json({ balance: 10, allowed: true, charged: true, price: 30 });
          }
          if (url.includes("/favorable/status")) {
            return Response.json({ chosen_event: null, chosen_custom: null, chosen_label: null, is_premium: false });
          }
          if (!url.includes("/favorable")) {
            return Response.json({});
          }
          const event = new URL(url, "http://local").searchParams.get("event");
          const note = event === "trip" ? "Дорога без спешки." : "Для спокойного и открытого разговора.";
          const suit = event === "trip" ? "Поездка" : "Встреча";
          return Response.json({
            status: "ready",
            event,
            label: suit,
            month: "2025-08",
            timezone: "Europe/Moscow",
            access: opened ? "full" : "preview",
            price: opened ? 0 : 30,
            days: opened
              ? [
                  { date: "2025-08-12", start: "11:00", end: "14:00", note: "Короткий разговор." },
                  { date: "2025-08-15", start: "10:00", end: "13:00", note },
                ]
              : [{ date: "2025-08-12", start: "11:00", end: "14:00", note: "Короткий разговор." }],
          });
        }),
      );
      renderAt(<FavorableDateScreen />);
      await userEvent.click(screen.getByRole("button", { name: "Встреча" }));
      expect(await screen.findByRole("heading", { name: "12 августа" })).toBeInTheDocument();
      expect(screen.getByText("Подходит для встречи")).toBeInTheDocument();
      expect(screen.getByText("Лучшее время · 11:00–14:00")).toBeInTheDocument();
      expect(screen.getByText(/Ближайший день бесплатно/)).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: /Открыть за/ }));
      expect(await screen.findByRole("button", { name: "15, благоприятный день" })).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "15, благоприятный день" }));
      expect(screen.getByRole("heading", { name: "15 августа" })).toBeInTheDocument();
      expect(screen.getByText("Для спокойного и открытого разговора.")).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Добавить в календарь" }));
      expect(createObjectURL).toHaveBeenCalled();
      await userEvent.click(screen.getByRole("button", { name: "Поездка" }));
      expect(await screen.findByText("Дорога без спешки.")).toBeInTheDocument();
      expect(screen.getByText("Подходит для поездки")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
      vi.restoreAllMocks();
      vi.unstubAllGlobals();
    }
  });

  it("limits free favorable view to one category per day", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/favorable/status")) {
          return Response.json({ chosen_event: "meeting", chosen_custom: null, chosen_label: "Встреча", is_premium: false });
        }
        if (!url.includes("/favorable")) {
          return Response.json({});
        }
        const event = new URL(url, "http://local").searchParams.get("event");
        if (event === "meeting") {
          return Response.json({
            status: "ready",
            event: "meeting",
            label: "Встреча",
            month: "2025-08",
            timezone: "Europe/Moscow",
            access: "preview",
            price: 30,
            days: [{ date: "2025-08-12", start: "11:00", end: "14:00", note: "Короткий разговор." }],
          });
        }
        return Response.json({
          status: "ready",
          event,
          label: "Поездка",
          month: "2025-08",
          timezone: "Europe/Moscow",
          access: "locked",
          price: 30,
          days: [],
          free_chosen_label: "Встреча",
        });
      }),
    );
    renderAt(<FavorableDateScreen />);
    expect(await screen.findByRole("heading", { name: "12 августа" })).toBeInTheDocument();
    expect(screen.getByText("Подходит для встречи")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Поездка" }));
    expect(await screen.findByRole("heading", { name: "Категория недоступна бесплатно" })).toBeInTheDocument();
    expect(screen.getByText(/Сегодня вы уже выбрали «Встреча»/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Встреча" }));
    expect(await screen.findByRole("heading", { name: "12 августа" })).toBeInTheDocument();
  });

  it("opens the relative form from the profile list", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[{ pathname: "/people", state: { add: true } }]}>
          <PeopleScreen />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByRole("heading", { name: "Близкие" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Имя" })).toBeInTheDocument();
  });
});
