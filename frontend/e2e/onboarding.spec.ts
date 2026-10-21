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

test("onboarding keeps the name, reports a bad date, and returns the sign", async ({ page }) => {
  const raw = initData();
  await page.route("https://telegram.org/js/telegram-web-app.js", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/javascript",
      body: "/* test bridge stays in the playwright browser */",
    });
  });
  await page.addInitScript((value: string) => {
    const button = {
      show() {},
      hide() {},
      onClick(handler: () => void) {
        this.handler = handler;
      },
      offClick() {
        this.handler = null;
      },
      handler: null as null | (() => void),
    };
    window.Telegram = {
      WebApp: {
        initData: value,
        ready() {},
        expand() {},
        BackButton: button,
        enableClosingConfirmation() {},
        disableClosingConfirmation() {},
        onEvent() {},
        offEvent() {},
      },
    };
  }, raw);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "добро пожаловать" })).toBeVisible();
  await page.getByRole("button", { name: "далее" }).click();
  await page.getByLabel("как к вам обращаться").fill("Мария");
  await page.getByRole("button", { name: "далее" }).click();
  await page.getByLabel("дата рождения").fill("32.13.1990");
  await page.getByRole("button", { name: "далее" }).click();
  await expect(page.getByRole("alert")).toContainText("дата в формате дд.мм.гггг");
  await page.getByRole("button", { name: "назад" }).click();
  await expect(page.getByLabel("как к вам обращаться")).toHaveValue("Мария");
  await page.getByRole("button", { name: "далее" }).click();
  await page.getByLabel("дата рождения").fill("02.01.1990");
  await page.getByRole("button", { name: "далее" }).click();
  await page.getByRole("button", { name: "не знаю" }).click();
  await page.getByRole("button", { name: "далее" }).click();
  const sign = page.getByRole("img", { name: "козерог" });
  const profile = page.getByRole("button", { name: "профиль" });
  await expect(sign).toBeVisible();
  await expect(profile).toBeVisible();
  await expect(page.getByText("развлекательный материал, без обещания точных событий")).toBeVisible();
  const signBox = await sign.boundingBox();
  const profileBox = await profile.boundingBox();
  expect(signBox).not.toBeNull();
  expect(profileBox).not.toBeNull();
  expect(signBox!.x + signBox!.width).toBeLessThanOrEqual(profileBox!.x + 4);
  await page.getByRole("button", { name: "карта" }).click();
  await expect(page.getByRole("heading", { name: "карта" })).toBeVisible();
  await expect(page.getByText("время рождения неизвестно")).toBeVisible();
  await expect(page.getByRole("heading", { name: "этот разбор в premium" })).toBeVisible();
  await expect(page.getByText("точный лунный знак не определён")).toBeVisible();
  await expect(page.getByText("развлекательный материал, без обещания точных событий")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.mouse.move(4, 420);
  await page.mouse.down();
  await page.mouse.move(150, 428, { steps: 12 });
  await page.mouse.up();
  await expect(page.getByRole("button", { name: "карта" })).toBeVisible();
  await expect(page.getByText("развлекательный материал, без обещания точных событий")).toBeVisible();
  await profile.click();
  await expect(page.getByRole("heading", { name: "профиль" })).toBeVisible();
  await expect(page.getByRole("button", { name: "не знаю" })).toHaveCount(0);
  const remove = page.getByRole("button", { name: "удалить данные" });
  const save = page.getByRole("button", { name: "сохранить" });
  await expect(remove).toBeVisible();
  const removeBox = await remove.boundingBox();
  const saveBox = await save.boundingBox();
  expect(removeBox).not.toBeNull();
  expect(saveBox).not.toBeNull();
  expect(removeBox!.y).toBeGreaterThan(saveBox!.y + 40);
  await expect(remove).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(remove).toHaveCSS("color", "rgb(155, 45, 48)");
  await remove.hover();
  await expect(remove).toHaveCSS("background-color", "rgb(155, 45, 48)");
  await expect(remove).toHaveCSS("color", "rgb(245, 240, 240)");
  await page.mouse.move(4, 420);
  await page.mouse.down();
  await page.mouse.move(150, 424, { steps: 12 });
  await page.mouse.up();
  await expect(page.getByRole("button", { name: "карта" })).toBeVisible();
});
