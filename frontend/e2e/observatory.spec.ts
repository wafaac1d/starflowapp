import { expect, test, type Page } from "@playwright/test";

function profile(step: string) {
  return {
    user_id: "00000000-0000-0000-0000-000000000001",
    is_admin: false,
    is_premium: false,
    step,
    display_name: step === "welcome" || step === "name" || step === "date" ? null : "Анна",
    birth_date: step === "done" ? "12.08.1995" : null,
    birth_time: step === "done" ? "14:30" : null,
    birth_time_unknown: false,
    timezone: step === "done" ? "Europe/Moscow" : null,
    birth_place: null,
    latitude: null,
    longitude: null,
    calendar_sign: step === "done" ? "Лев" : null,
  };
}

async function installApp(page: Page, step = "done") {
  let current = profile(step);
  await page.route("**/*telegram-web-app.js", (route) =>
    route.fulfill({ contentType: "application/javascript", body: "" }),
  );
  await page.addInitScript(() => {
    const fixed = Date.parse("2025-08-12T21:00:00+03:00");
    const RealDate = Date;
    class FixedDate extends RealDate {
      constructor(...args: ConstructorParameters<typeof Date>) {
        if (args.length === 0) {
          super(fixed);
          return;
        }
        super(...args);
      }

      static override now(): number {
        return fixed;
      }
    }
    window.Date = FixedDate;
    const user = encodeURIComponent(JSON.stringify({ first_name: "Анна" }));
    window.Telegram = {
      WebApp: {
        initData: `auth_date=1&hash=abc&user=${user}`,
        ready() {},
        expand() {},
        colorScheme: "dark",
      },
    };
  });
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (url.includes("/session")) {
      await route.fulfill({ json: current });
      return;
    }
    if (url.includes("/profile/draft")) {
      const body = JSON.parse(route.request().postData() ?? "{}") as Record<string, unknown>;
      if (typeof body.display_name === "string") {
        current = { ...current, step: "date", display_name: body.display_name };
      } else if (typeof body.birth_date === "string") {
        current = { ...current, step: "time", birth_date: body.birth_date };
      } else if (typeof body.birth_time === "string" || body.birth_time_unknown === true) {
        current = {
          ...current,
          step: "timezone",
          birth_time: typeof body.birth_time === "string" ? body.birth_time : null,
          birth_time_unknown: body.birth_time_unknown === true,
        };
      } else if (typeof body.timezone === "string") {
        current = {
          ...current,
          step: "done",
          timezone: body.timezone,
          display_name: current.display_name ?? "Анна",
          birth_date: current.birth_date ?? "12.08.1995",
          birth_time: current.birth_time ?? "14:30",
          calendar_sign: "Лев",
        };
      }
      await route.fulfill({ json: current });
      return;
    }
    if (url.includes("/readings/")) {
      await route.fulfill({
        json: {
          status: "ready",
          title: "День для ясных решений",
          body: "Сегодня благоприятный день для важных разговоров и новых начинаний. Доверяйте интуиции — она подскажет верное направление.",
          greeting: null,
          user_sign: "Лев",
          shared_facts: null,
          history_id: "hist-1",
          streak: null,
          replayed: false,
          reset_at: null,
        },
      });
      return;
    }
    if (url.includes("/chart")) {
      await route.fulfill({
        json: {
          sun_sign: "Лев",
          sun_sign_source: "date",
          moon_sign: "Рыбы",
          ascendant_sign: "Скорпион",
          houses: null,
          planets: [],
          aspects: [],
          transits: [],
          lunar_day: 1,
          phase_name: null,
          limitations: [],
          natal_access: "ready",
        },
      });
      return;
    }
    if (url.includes("/related") && method === "GET") {
      await route.fulfill({
        json: [
          { related_id: "mama", display_name: "Мама", birth_date: "14.03.1968" },
          { related_id: "daniil", display_name: "Даниил", birth_date: "22.11.1988" },
          { related_id: "sergey", display_name: "Сергей", birth_date: "17.06.1992" },
        ],
      });
      return;
    }
    if (url.includes("/assistant/messages") && method === "GET") {
      await route.fulfill({
        json: {
          remaining: 18,
          messages: [
            {
              id: "u1",
              role: "user",
              content: "На чём сосредоточиться сегодня?",
              created_at: "2025-08-12T09:41:00",
            },
            {
              id: "b1",
              role: "assistant",
              content:
                "Сегодня важно сохранять спокойствие и не спешить с решениями. Хороший день для планирования и общения с близкими. Избегайте перегрузок.",
              created_at: "2025-08-12T09:41:00",
            },
          ],
        },
      });
      return;
    }
    if (url.includes("/assistant/messages") && method === "POST") {
      await route.fulfill({
        json: { status: "ready", reply: "Спокойный вечер.", remaining: 4, replayed: false, code: null },
      });
      return;
    }
    if (url.includes("/notifications") && method === "GET") {
      await route.fulfill({
        json: { local_time: "08:30", timezone: "Europe/Moscow", day: true, moon: false, retro: false },
      });
      return;
    }
    if (url.includes("/notifications") && method === "PUT") {
      await route.fulfill({ json: JSON.parse(route.request().postData() ?? "{}") });
      return;
    }
    if (url.includes("/billing")) {
      await route.fulfill({
        json: {
          price_stars: 250,
          period_days: 30,
          premium: false,
          subscription_invoice_link: null,
          subscription_order_id: null,
          subscription_payment_state: "none",
        },
      });
      return;
    }
    if (url.includes("/share/")) {
      await route.fulfill({ json: { text: "https://example.test/share" } });
      return;
    }
    await route.fulfill({ json: [] });
  });
}

async function openReady(page: Page, path: string) {
  await installApp(page, "done");
  await page.goto(path);
}

test("onboarding leads to today and the forecast period changes", async ({ page }) => {
  await installApp(page, "welcome");
  await page.goto("/");
  await page.getByRole("button", { name: "Начать" }).click();
  await expect(page.getByRole("heading", { name: "Когда вы родились?" })).toBeVisible();
  await page.getByRole("textbox", { name: "Дата рождения" }).fill("12.08.1995");
  await page.getByRole("textbox", { name: "Время рождения" }).fill("14:30");
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.getByRole("heading", { name: "Анна" })).toBeVisible();
  await expect(page.getByText("Добрый вечер,")).toBeVisible();
  await page.getByRole("button", { name: "Открыть прогноз" }).click();
  await expect(page.getByRole("heading", { name: "Ваш прогноз" })).toBeVisible();
  await page.getByRole("tab", { name: "Неделя" }).click();
  await expect(page.getByRole("tab", { name: "Неделя" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Месяц" }).click();
  await expect(page.getByRole("tab", { name: "Месяц" })).toHaveAttribute("aria-selected", "true");
});

test("tab bar, calendar, chat, settings and paywall", async ({ page }) => {
  await openReady(page, "/");
  await page.getByRole("link", { name: "Календарь" }).click();
  await expect(page.getByRole("heading", { name: "Лунный календарь" })).toBeVisible();
  await page.goto("/calendar?day=2025-08-01");
  await page.getByRole("button", { name: "12" }).click();
  await expect(page.getByText("12 августа 2025")).toBeVisible();
  await page.getByRole("link", { name: "Чат" }).click();
  await page.getByRole("textbox", { name: "Написать сообщение…" }).fill("Что важно вечером?");
  await page.getByRole("button", { name: "отправить" }).click();
  await expect(page.getByText("Спокойный вечер.")).toBeVisible();
  await page.goto("/settings");
  const daily = page.getByRole("switch", { name: "Ежедневный прогноз" });
  await daily.click();
  await expect(daily).not.toBeChecked();
  await page.goto("/profile");
  await page.getByRole("link", { name: "Моя подписка" }).click();
  await expect(page.getByRole("heading", { name: "Больше о себе" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "разделы" })).toHaveCount(0);
});

const SHOTS: { name: string; path: string }[] = [
  { name: "welcome", path: "/welcome" },
  { name: "birth", path: "/onboarding/birth" },
  { name: "today", path: "/" },
  { name: "forecast", path: "/forecast" },
  { name: "calendar", path: "/calendar?day=2025-08-12" },
  { name: "natal", path: "/natal" },
  { name: "compatibility", path: "/compatibility/mikhail" },
  { name: "chat", path: "/chat" },
  { name: "people", path: "/people" },
  { name: "profile", path: "/profile" },
  { name: "settings", path: "/settings" },
  { name: "premium", path: "/premium" },
];

for (const shot of SHOTS) {
  test(`screenshot ${shot.name}`, async ({ page }) => {
    await installApp(page, shot.name === "welcome" ? "welcome" : "done");
    await page.goto(shot.path);
    await expect(page.locator("body")).toBeVisible();
    await expect(page).toHaveScreenshot(`${shot.name}.png`, { animations: "disabled" });
  });
}
