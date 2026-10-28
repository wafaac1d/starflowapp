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
    star_balance: 0,
  };
}

async function installApp(page: Page, step = "done", premium = false) {
  let current = { ...profile(step), is_premium: premium };
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
    if (url.includes("/stars/spends") && method === "POST") {
      await route.fulfill({
        json: { balance: current.star_balance, allowed: true, charged: false, price: 40 },
      });
      return;
    }
    if (url.includes("/stars/topups") && method === "POST") {
      await route.fulfill({
        json: {
          order_id: "00000000-0000-0000-0000-0000000000aa",
          invoice_link: "https://t.me/invoice/test",
          balance: current.star_balance,
          amount: 10,
        },
      });
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
    if (method === "PATCH" && url.includes("/profile")) {
      const body = JSON.parse(route.request().postData() ?? "{}") as Record<string, unknown>;
      const unknown = body.birth_time_unknown === true;
      current = {
        ...current,
        birth_date: typeof body.birth_date === "string" ? body.birth_date : current.birth_date,
        birth_time: unknown
          ? null
          : typeof body.birth_time === "string"
            ? body.birth_time
            : current.birth_time,
        birth_time_unknown: unknown,
      };
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
    if (url.includes("/related") && method === "POST") {
      const body = JSON.parse(route.request().postData() ?? "{}") as Record<string, unknown>;
      await route.fulfill({
        json: {
          related_id: "new-person",
          display_name: body.display_name,
          birth_date: body.birth_date,
          birth_time: typeof body.birth_time === "string" ? body.birth_time : null,
          birth_time_unknown: body.birth_time_unknown !== false,
          consent: body.consent === true,
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
    if (url.includes("/retro") && method === "GET") {
      await route.fulfill({
        json: [
          { planet: "меркурий", start: "2025-08-01", end: "2025-08-25" },
          { planet: "сатурн", start: "2025-07-26", end: "2025-12-10" },
          { planet: "венера", start: "2025-09-01", end: "2025-09-20" },
        ],
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
    if (url.includes("/favorites/") && method === "GET") {
      const historyId = url.split("/favorites/")[1]?.split("?")[0] ?? "";
      await route.fulfill({
        json: {
          history_id: historyId,
          title: "День для ясных решений",
          body: "Сегодня благоприятный день для важных разговоров и новых начинаний.",
        },
      });
      return;
    }
    if (url.includes("/favorites") && method === "GET") {
      await route.fulfill({
        json: [
          { history_id: "11111111-1111-1111-1111-111111111111", title: "День для ясных решений" },
          { history_id: "22222222-2222-2222-2222-222222222222", title: "Неделя спокойных дел" },
        ],
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

async function openReady(page: Page, path: string, premium = false) {
  await installApp(page, "done", premium);
  await page.goto(path);
}

test("today opens retrograde planets", async ({ page }) => {
  await openReady(page, "/");
  const practices = page.getByRole("heading", { name: "Ваши астропрактики" });
  await practices.scrollIntoViewIfNeeded();
  await expect(practices).toBeVisible();
  const badge = page.getByText("2 периода");
  await badge.scrollIntoViewIfNeeded();
  await expect(badge).toBeVisible();
  await page.getByRole("button", { name: "Ретроградные планеты" }).click();
  await expect(page.getByRole("heading", { name: "Ретроградные планеты" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Меркурий" })).toBeVisible();
  await expect(page.getByText("Ретроградный").first()).toBeVisible();
  await page.getByRole("tab", { name: "Скоро" }).click();
  await expect(page.getByRole("heading", { name: "Венера" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Меркурий" })).toHaveCount(0);
  await page.getByRole("button", { name: "Напомнить о периоде" }).click();
  await expect(page.getByRole("button", { name: "Напоминание включено" })).toBeDisabled();
});

test("today content starts below the telegram header", async ({ page }) => {
  await openReady(page, "/");
  await page.evaluate(() => {
    const root = document.documentElement;
    root.style.setProperty("--tg-safe-area-inset-top", "47px");
    root.style.setProperty("--tg-content-safe-area-inset-top", "56px");
  });
  const greeting = page.getByText("Добрый вечер,");
  await expect(greeting).toBeVisible();
  const box = await greeting.boundingBox();
  expect(box).not.toBeNull();
  expect(box?.y ?? 0).toBeGreaterThanOrEqual(47 + 56);
  const profile = page.getByRole("button", { name: "Баланс 0" });
  const profileBox = await profile.boundingBox();
  expect(profileBox?.y ?? 0).toBeGreaterThanOrEqual(47 + 56);
  await profile.click();
  const topUp = page.getByRole("dialog", { name: "Пополнение" });
  await expect(topUp).toBeVisible();
  await expect(topUp.getByRole("button", { name: /^10$/ })).toHaveAttribute("aria-pressed", "true");
  await expect(topUp.getByRole("button", { name: "20" })).toBeVisible();
  await expect(topUp.getByRole("button", { name: "50" })).toBeVisible();
  await expect(topUp.getByRole("button", { name: "100" })).toBeVisible();
  await expect(topUp.getByRole("button", { name: "Оплатить" })).toBeEnabled();
  await expect(topUp.getByRole("textbox", { name: "Код" })).toBeVisible();
  await expect(topUp.getByRole("button", { name: "Активировать" })).toBeDisabled();
  await expect(topUp.getByRole("link", { name: /^Premium$/ })).toHaveAttribute("href", "/premium");
  await expect(topUp.getByRole("link", { name: "t.me/PremiumBot" })).toHaveAttribute(
    "href",
    "https://t.me/PremiumBot",
  );
  await topUp.getByRole("button", { name: "Закрыть" }).click();
  await expect(topUp).toHaveCount(0);
});

test("premium balance shows unlim and the star count", async ({ page }) => {
  await installApp(page, "done", true);
  await page.goto("/");
  const balance = page.getByRole("button", { name: "Баланс unlim/0" });
  await expect(balance).toBeVisible();
  const unlim = balance.getByText("unlim", { exact: true });
  const rest = balance.getByText("/0", { exact: true });
  await expect(unlim).toHaveText("unlim");
  await expect(rest).toHaveText("/0");
  const sizes = await Promise.all([
    unlim.evaluate((node) => getComputedStyle(node).fontSize),
    rest.evaluate((node) => getComputedStyle(node).fontSize),
  ]);
  expect(sizes[0]).toBe("15px");
  expect(sizes[1]).toBe("13px");
  const offset = await balance.evaluate((node) => {
    const button = node.getBoundingClientRect();
    const pieces = [...node.querySelectorAll("span")].map((piece) => piece.getBoundingClientRect());
    const left = Math.min(...pieces.map((piece) => piece.left));
    const right = Math.max(...pieces.map((piece) => piece.right));
    const top = Math.min(...pieces.map((piece) => piece.top));
    const bottom = Math.max(...pieces.map((piece) => piece.bottom));
    return {
      dx: (left + right) / 2 - (button.left + button.width / 2),
      dy: (top + bottom) / 2 - (button.top + button.height / 2),
    };
  });
  expect(Math.abs(offset.dx)).toBeLessThan(1);
  expect(Math.abs(offset.dy)).toBeLessThan(1);
});

test("premium can be paid from the star balance", async ({ page }) => {
  await openReady(page, "/premium");
  const pay = page.getByRole("button", { name: "Списать 250 с баланса" });
  await pay.scrollIntoViewIfNeeded();
  await expect(pay).toBeVisible();
  await expect(page.getByText("Разовое списание с баланса, без автопродления.")).toBeVisible();
});

test("adding a person keeps equal gaps and the list waits with row silhouettes", async ({ page }) => {
  let release = () => undefined;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await installApp(page, "done");
  await page.route("**/api/v1/related**", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }
    await gate;
    await route.fallback();
  });
  await page.goto("/people");
  const silhouettes = page.locator("div[aria-hidden='true'] > span");
  await expect(silhouettes).toHaveCount(3);
  const shine = await silhouettes.first().evaluate((node) => getComputedStyle(node, "::after").animationName);
  expect(shine).toContain("skeleton-shine");
  release();
  await expect(page.getByRole("button", { name: /Мама/ })).toBeVisible();
  await page.getByRole("button", { name: "Добавить человека" }).click();
  const name = page.getByRole("textbox", { name: "Имя" }).locator("xpath=ancestor::label");
  const born = page.getByRole("textbox", { name: "Дата рождения" }).locator("xpath=ancestor::label");
  const save = page.getByRole("button", { name: "Сохранить" });
  const add = page.getByRole("button", { name: "Добавить человека" });
  await expect(name).toBeVisible();
  const boxes = await Promise.all([name.boundingBox(), born.boundingBox(), save.boundingBox(), add.boundingBox()]);
  const gaps = boxes.flatMap((box, index) => {
    const next = boxes[index + 1];
    if (box === null || next === null || next === undefined) {
      return [];
    }
    return [Math.round(next.y - (box.y + box.height))];
  });
  expect(gaps).toEqual([24, 24, 24]);
});

test("a saved forecast stays saved and opens from favorites", async ({ page }) => {
  await installApp(page, "done");
  await page.route("**/api/v1/favorites", async (route) => {
    if (route.request().method() !== "GET" || route.request().url().includes("/favorites/")) {
      await route.fallback();
      return;
    }
    await route.fulfill({
      json: [{ history_id: "hist-1", title: "День для ясных решений" }],
    });
  });
  await page.goto("/forecast");
  await expect(page.getByRole("button", { name: "Сохранено" })).toBeDisabled();
  await page.goto("/favorites");
  await page.getByRole("link", { name: "День для ясных решений" }).click();
  await expect(page.getByRole("heading", { name: "День для ясных решений" })).toBeVisible();
  await expect(page.getByText(/благоприятный день/)).toBeVisible();
});

test("onboarding accepts an untouched birth time", async ({ page }) => {
  await installApp(page, "welcome");
  await page.goto("/");
  await page.getByRole("button", { name: "Начать" }).click();
  await expect(page.getByText("Можно оставить пустым, если не знаете время рождения")).toBeVisible();
  await page.getByRole("textbox", { name: "Дата рождения" }).fill("12.08.1995");
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.getByRole("heading", { name: "Анна" })).toBeVisible();
});

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

test("a free topic opens the premium alert", async ({ page }) => {
  await openReady(page, "/");
  await page.getByRole("button", { name: "Любовь" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("Эта функция только с Premium.");
  await page.getByRole("button", { name: "Понятно" }).click();
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await page.goto("/forecast");
  await page.getByRole("button", { name: /Отношения/ }).click();
  await expect(page.getByRole("alertdialog")).toContainText("Эта функция только с Premium.");
});

test("today opens compatibility without a saved person", async ({ page }) => {
  await openReady(page, "/");
  await page.getByRole("button", { name: "Совместимость" }).click();
  await expect(page.getByRole("heading", { name: "Совместимость" })).toBeVisible();
  const second = page.getByRole("region", { name: "Второй человек" });
  await second.getByRole("textbox", { name: "Имя" }).fill("Михаил");
  await second.getByRole("textbox", { name: "Дата рождения" }).fill("03.05.1993");
  await expect(page.getByRole("button", { name: "Проверить" })).toBeEnabled();
  await expect(page.getByText("Глубокая связь")).toHaveCount(0);
  const saved = page.waitForRequest(
    (request) => request.method() === "POST" && request.url().includes("/api/v1/related"),
  );
  await page.getByRole("switch", { name: "Сохранить в близкие" }).click();
  expect((await saved).postDataJSON()).toMatchObject({
    display_name: "Михаил",
    birth_date: "03.05.1993",
    birth_time_unknown: true,
    consent: true,
  });
  await page.getByRole("button", { name: "Проверить" }).click();
  await expect(page.getByRole("status")).toContainText("Связь со звёздами");
  await expect(page.getByText("Телец")).toBeVisible();
  await expect(page.getByText("Глубокая связь")).toBeVisible();
  await expect(page.locator("img[src='/illustrations/png/compatibility_diagram.png']")).toBeVisible();
});

test("empty chat explains itself in the middle", async ({ page }) => {
  await installApp(page);
  await page.route("**/api/v1/assistant/messages", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: { messages: [], remaining: 18 } });
      return;
    }
    await route.fallback();
  });
  await page.goto("/chat");
  const note = page.getByText(/Это чат с астропомощником/);
  await expect(note).toBeVisible();
  await expect(note).toContainText("20");
  await expect(page.getByText("звёзд за вопрос")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Недостаточно звёзд" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Отправить" })).toBeDisabled();
  const box = await note.boundingBox();
  const center = (box?.y ?? 0) + (box?.height ?? 0) / 2;
  expect(center).toBeGreaterThan(280);
  expect(center).toBeLessThan(640);
});

test("chat field stays visible when the dialog is scrolled", async ({ page }) => {
  await installApp(page, "done", true);
  await page.route("**/api/v1/assistant/messages", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }
    const messages = Array.from({ length: 20 }, (_, index) => ({
      id: `m${index}`,
      role: index % 2 === 0 ? "user" : "assistant",
      content: `Строка ${index}. `.repeat(6),
      created_at: "2025-08-12T09:41:00",
    }));
    await route.fulfill({ json: { remaining: 18, messages } });
  });
  await page.goto("/chat");
  const log = page.getByRole("log", { name: "Диалог" });
  const field = page.getByRole("textbox", { name: "Написать сообщение…" });
  await expect(field).toBeVisible();
  await log.evaluate((node) => {
    node.scrollTop = 0;
  });
  const box = await field.boundingBox();
  const height = page.viewportSize()?.height ?? 0;
  expect(box).not.toBeNull();
  expect((box?.y ?? 0) + (box?.height ?? 0)).toBeGreaterThan(height - 180);
  expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThan(height - 70);
  const avatar = page.locator("img[src*='assistant_avatar']").first();
  const bubble = page.getByText(/^Строка 1\./);
  const avatarBox = await avatar.boundingBox();
  const bubbleBox = await bubble.boundingBox();
  expect(avatarBox).not.toBeNull();
  expect(bubbleBox).not.toBeNull();
  const avatarBottom = (avatarBox?.y ?? 0) + (avatarBox?.height ?? 0);
  const bubbleBottom = (bubbleBox?.y ?? 0) + (bubbleBox?.height ?? 0);
  expect(Math.abs(avatarBottom - bubbleBottom)).toBeLessThan(8);
  expect(avatarBox?.y ?? 0).toBeGreaterThan((bubbleBox?.y ?? 0) + 12);
});

test("chat shows the sent line before the model answers", async ({ page }) => {
  await installApp(page, "done", true);
  let release: () => void = () => undefined;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/assistant/messages", async (route) => {
    if (route.request().method() === "POST") {
      await gate;
      await route.fulfill({
        json: { status: "ready", reply: "Спокойный вечер.", remaining: 17, replayed: false, code: "ready" },
      });
      return;
    }
    await route.fallback();
  });
  await page.goto("/chat");
  await page.getByRole("textbox", { name: "Написать сообщение…" }).fill("Что вечером?");
  await page.getByRole("button", { name: "Отправить" }).click();
  await expect(page.getByText("Что вечером?")).toBeVisible();
  await expect(page.getByRole("status", { name: "Астропомощник отвечает" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Написать сообщение…" })).toHaveValue("");
  release();
  await expect(page.getByText("Спокойный вечер.")).toBeVisible();
  await expect(page.getByRole("status", { name: "Астропомощник отвечает" })).toHaveCount(0);
  await expect(page.getByText("Что вечером?")).toBeVisible();
});

test("profile edit saves the birth time and an empty field means unknown", async ({ page }) => {
  await openReady(page, "/profile");
  await page.getByRole("link", { name: "Данные рождения" }).click();
  await expect(page.getByRole("heading", { name: "Когда вы родились?" })).toBeVisible();
  await expect(page.getByRole("switch", { name: "Не знаю время" })).toHaveCount(0);
  const time = page.getByRole("textbox", { name: "Время рождения" });
  await time.fill("09:15");
  const saved = page.waitForRequest(
    (request) => request.method() === "PATCH" && request.url().includes("/api/v1/profile"),
  );
  await page.getByRole("button", { name: "Продолжить" }).click();
  expect((await saved).postDataJSON()).toMatchObject({
    birth_date: "12.08.1995",
    birth_time: "09:15",
    birth_time_unknown: false,
  });
  await expect(page.getByRole("heading", { name: "Анна" })).toBeVisible();

  await page.getByRole("link", { name: "Профиль" }).click();
  await page.getByRole("link", { name: "Данные рождения" }).click();
  await page.getByRole("textbox", { name: "Время рождения" }).fill("");
  const cleared = page.waitForRequest(
    (request) => request.method() === "PATCH" && request.url().includes("/api/v1/profile"),
  );
  await page.getByRole("button", { name: "Продолжить" }).click();
  expect((await cleared).postDataJSON()).toEqual({
    birth_date: "12.08.1995",
    birth_time_unknown: true,
  });
});

test("tab bar, calendar, chat, settings and paywall", async ({ page }) => {
  await openReady(page, "/", true);
  await page.getByRole("button", { name: "Натальная карта" }).click();
  await expect(page.getByRole("heading", { name: "Натальная карта" })).toBeVisible();
  await page.getByRole("link", { name: "Календарь" }).click();
  await expect(page.getByRole("heading", { name: "Лунный календарь" })).toBeVisible();
  await page.goto("/calendar?day=2025-08-01");
  await page.getByRole("button", { name: "12" }).click();
  await expect(page.getByText("12 августа 2025")).toBeVisible();
  await page.getByRole("link", { name: "Чат" }).click();
  await page.getByRole("textbox", { name: "Написать сообщение…" }).fill("Что важно вечером?");
  await page.getByRole("button", { name: "Отправить" }).click();
  await expect(page.getByText("Спокойный вечер.")).toBeVisible();
  await page.goto("/settings");
  const daily = page.getByRole("switch", { name: "Ежедневный прогноз" });
  await daily.click();
  await expect(daily).not.toBeChecked();
  await page.goto("/profile");
  await expect(page.getByRole("link", { name: "История" })).toHaveCount(0);
  await page.getByRole("link", { name: "Избранное" }).click();
  await expect(page.getByRole("heading", { name: "Избранное" })).toBeVisible();
  await expect(page.getByText("Неделя спокойных дел")).toBeVisible();
  await page.goto("/profile");
  await page.getByRole("link", { name: "Моя подписка" }).click();
  await expect(page.getByRole("heading", { name: "Больше о себе" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Разделы" })).toHaveCount(0);
});

test("add relative fields keep an even gap", async ({ page }) => {
  await openReady(page, "/profile");
  await page.getByRole("button", { name: "Добавить близкого" }).click();
  await expect(page.getByRole("textbox", { name: "Имя" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Дата рождения" })).toBeVisible();
  await expect(page).toHaveScreenshot("people-add.png", { animations: "disabled" });
});

const SHOTS: { name: string; path: string }[] = [
  { name: "welcome", path: "/welcome" },
  { name: "birth", path: "/onboarding/birth" },
  { name: "today", path: "/" },
  { name: "retro", path: "/retro" },
  { name: "forecast", path: "/forecast" },
  { name: "calendar", path: "/calendar?day=2025-08-12" },
  { name: "natal", path: "/natal" },
  { name: "compatibility", path: "/compatibility/mikhail" },
  { name: "chat", path: "/chat" },
  { name: "people", path: "/people" },
  { name: "profile", path: "/profile" },
  { name: "favorites", path: "/favorites" },
  { name: "settings", path: "/settings" },
  { name: "premium", path: "/premium" },
];

for (const shot of SHOTS) {
  test(`screenshot ${shot.name}`, async ({ page }) => {
    await installApp(page, shot.name === "welcome" ? "welcome" : "done");
    await page.goto(shot.path);
    await expect(page.locator("body")).toBeVisible();
    if (shot.name === "today") {
      await expect(page.getByRole("button", { name: "День для ясных решений" })).toBeVisible();
    }
    if (shot.name === "retro") {
      await expect(page.getByRole("heading", { name: "Меркурий" })).toBeVisible();
    }
    if (shot.name === "forecast") {
      await expect(page.getByText(/благоприятный день/)).toBeVisible();
    }
    if (shot.name === "natal") {
      await expect(page.getByText("Лев")).toBeVisible();
    }
    await expect(page).toHaveScreenshot(`${shot.name}.png`, { animations: "disabled" });
  });
}
