import { createHmac } from "node:crypto";

import { expect, test } from "@playwright/test";

const token = "123456:TESTTOKEN";

function initData(): string {
  const user = JSON.stringify({ id: 77, username: "maria" });
  const authDate = String(Math.floor(Date.now() / 1000));
  const values = [
    ["auth_date", authDate],
    ["query_id", "test-query"],
    ["user", user],
  ] as const;
  const check = [...values]
    .sort((left, right) => (left[0] < right[0] ? -1 : left[0] > right[0] ? 1 : 0))
    .map(([key, value]) => `${key}=${value}`)
    .join("\n");
  const secret = createHmac("sha256", "WebAppData").update(token).digest();
  const hash = createHmac("sha256", secret).update(check).digest("hex");
  const params = new URLSearchParams();
  for (const [key, value] of values) {
    params.append(key, value);
  }
  params.append("hash", hash);
  return params.toString();
}

const profile = {
  user_id: "00000000-0000-0000-0000-000000000077",
  is_admin: false,
  is_premium: true,
  step: "done",
  display_name: "Мария",
  birth_date: "1990-01-02",
  birth_time: null,
  birth_time_unknown: true,
  timezone: "Europe/Moscow",
  birth_place: null,
  latitude: null,
  longitude: null,
  calendar_sign: "козерог",
};

test("premium paths keep the question, the month and the paywall", async ({ page }) => {
  const raw = initData();
  await page.route("https://telegram.org/js/telegram-web-app.js", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/javascript",
      body: "/* test bridge stays in the playwright browser */",
    });
  });
  await page.addInitScript((value: string) => {
    window.Telegram = {
      WebApp: {
        initData: value,
        ready() {},
        expand() {},
        BackButton: { show() {}, hide() {}, onClick() {}, offClick() {} },
        enableClosingConfirmation() {},
        disableClosingConfirmation() {},
        onEvent() {},
        offEvent() {},
      },
    };
  }, raw);
  await page.route("**/api/v1/session", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(profile) });
  });
  await page.route("**/api/v1/assistant/messages**", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as { text: string };
      expect(body.text).toBe("Что с Луной?");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "ready",
          reply: "луна сегодня спокойная",
          remaining: 19,
          replayed: false,
          code: "ready",
        }),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/readings/personal_day**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "premium",
        title: null,
        body: "этот разбор в premium",
        greeting: null,
        user_sign: "козерог",
        shared_facts: null,
        history_id: null,
        streak: null,
        replayed: false,
        reset_at: null,
        days: [],
        limitations: [],
      }),
    });
  });
  await page.route("**/api/v1/readings/calendar**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ready",
        title: "февраль",
        body: "астрокалендарь",
        greeting: null,
        user_sign: null,
        shared_facts: null,
        history_id: null,
        streak: null,
        replayed: false,
        reset_at: null,
        days: [],
        limitations: ["owner_time_unknown"],
      }),
    });
  });

  await page.goto("/assistant");
  await expect(page.getByText("диалог пуст")).toBeVisible();
  await expect(page.getByText("фильтр не обещает")).toBeVisible();
  const input = page.getByLabel("помощник");
  await expect(input).toHaveCSS("text-transform", "none");
  const send = page.getByRole("button", { name: "отправить" });
  await expect(send).toBeDisabled();
  await input.fill("Что с Луной?");
  await expect(input).toHaveValue("Что с Луной?");
  await send.click();
  await expect(page.getByText("луна сегодня спокойная")).toBeVisible();
  await expect(page.getByText("19")).toBeVisible();

  await page.goto("/calendar/month?month=2024-02-10");
  await expect(page.getByRole("heading", { name: "февраль" })).toBeVisible();
  await expect(page.getByRole("list", { name: "легенда оценок" })).toBeVisible();
  await expect(page.getByText("низкая")).toBeVisible();
  await page.getByRole("button", { name: "следующий месяц" }).click();
  await expect(page.getByRole("heading", { name: "март" })).toBeVisible();

  await page.goto("/reading/personal_day");
  await expect(page.getByRole("alert")).toContainText("этот разбор в premium");
  await expect(page.getByRole("button", { name: "premium" })).toBeVisible();
});
