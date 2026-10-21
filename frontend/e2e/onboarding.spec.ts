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

  let releaseSession = () => {};
  const sessionGate = new Promise<void>((resolve) => {
    releaseSession = resolve;
  });
  await page.route("**/api/v1/session", async (route) => {
    await sessionGate;
    await route.continue();
  });

  await page.goto("/");
  const logo = page.getByRole("img", { name: "логотип starflow" });
  const loadingWord = page.locator(".loading-word");
  await expect(logo).toBeVisible();
  await expect(loadingWord).toContainText("загрузка");
  const logoBox = await logo.boundingBox();
  const wordBox = await loadingWord.boundingBox();
  expect(logoBox).not.toBeNull();
  expect(wordBox).not.toBeNull();
  expect(Math.abs(logoBox!.x + logoBox!.width / 2 - (wordBox!.x + wordBox!.width / 2))).toBeLessThan(6);
  releaseSession();
  const begin = page.getByRole("button", { name: "начать" });
  const startLogo = page.getByRole("img", { name: "логотип starflow" });
  const phrase = page.locator(".start-phrase");
  await expect(begin).toBeVisible();
  await expect(page.getByRole("heading", { name: "добро пожаловать" })).toHaveCount(0);
  await expect(phrase).toBeVisible();
  await expect(phrase).toHaveCSS("color", "rgb(184, 184, 184)");
  const startMain = await page.locator("main").boundingBox();
  const startLogoBox = await startLogo.boundingBox();
  const beginBox = await begin.boundingBox();
  const phraseBox = await phrase.boundingBox();
  expect(startMain).not.toBeNull();
  expect(startLogoBox).not.toBeNull();
  expect(beginBox).not.toBeNull();
  expect(phraseBox).not.toBeNull();
  expect(startLogoBox!.y + startLogoBox!.height).toBeLessThanOrEqual(beginBox!.y);
  expect(
    Math.abs(beginBox!.x + beginBox!.width / 2 - (startMain!.x + startMain!.width / 2)),
  ).toBeLessThan(8);
  expect(phraseBox!.y).toBeGreaterThan(beginBox!.y + beginBox!.height);
  expect(phraseBox!.y + phraseBox!.height).toBeGreaterThan(startMain!.y + startMain!.height - 96);
  await begin.click();
  const welcome = page.getByRole("heading", { name: "добро пожаловать" });
  await expect(welcome).toBeVisible();
  await expect(page.locator(".surface")).toHaveCount(0);
  await expect(welcome).toHaveCSS("text-align", "left");
  const welcomeBox = await page.locator(".onboarding-body").boundingBox();
  const welcomeMain = await page.locator("main").boundingBox();
  expect(welcomeBox).not.toBeNull();
  expect(welcomeMain).not.toBeNull();
  expect(
    Math.abs(
      welcomeBox!.y + welcomeBox!.height / 2 - (welcomeMain!.y + welcomeMain!.height / 2),
    ),
  ).toBeLessThan(80);
  await page.getByRole("button", { name: "далее" }).click();
  await expect(page.getByRole("heading", { name: "как к вам обращаться?" })).toBeVisible();
  await expect(page.getByText("как к вам обращаться", { exact: true })).toHaveCount(0);
  await page.getByLabel("как к вам обращаться?").fill("Мария");
  await expect(page.getByRole("button", { name: "отмена" })).toHaveCount(0);
  await page.getByRole("button", { name: "далее" }).click();
  const birthDate = page.getByLabel("дата рождения");
  await birthDate.pressSequentially("32131990");
  await expect(birthDate).toHaveValue("32.13.1990");
  await page.getByRole("button", { name: "далее" }).click();
  await expect(page.getByRole("alert")).toContainText("дата в формате дд.мм.гггг");
  await expect(page.getByRole("button", { name: "отмена" })).toHaveCount(0);
  await page.getByRole("button", { name: "назад" }).click();
  await expect(page.getByLabel("как к вам обращаться?")).toHaveValue("Мария");
  await page.getByRole("button", { name: "далее" }).click();
  await birthDate.pressSequentially("02011990");
  await expect(birthDate).toHaveValue("02.01.1990");
  await page.getByRole("button", { name: "далее" }).click();
  await expect(page.getByRole("button", { name: "не знаю" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "время рождения" })).toBeVisible();
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
  const plan = page.getByRole("img", { name: "бесплатная" });
  const tray = page.locator(".profile-tray");
  const planBox = await plan.boundingBox();
  const trayBox = await tray.boundingBox();
  const mainBox = await page.locator("main").boundingBox();
  expect(planBox).not.toBeNull();
  expect(trayBox).not.toBeNull();
  expect(mainBox).not.toBeNull();
  expect(profileBox!.x + profileBox!.width).toBeLessThanOrEqual(planBox!.x + 4);
  expect(planBox!.x + planBox!.width).toBeLessThanOrEqual(trayBox!.x + trayBox!.width + 1);
  expect(Math.abs(trayBox!.x + trayBox!.width / 2 - (mainBox!.x + mainBox!.width / 2))).toBeLessThan(8);
  const settings = page.getByRole("button", { name: "настройки" });
  await expect(settings).toHaveClass(/tile/);
  await expect(settings).toContainText("⚙️");
  const support = page.getByRole("button", { name: "поддержка платежей" });
  await expect(support).toHaveClass(/tile/);
  await expect(support).toContainText("💬");
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
  await page.getByRole("button", { name: "сегодня" }).click();
  await expect(page.getByRole("heading", { name: "сегодня" })).toBeVisible();
  await expect(page.getByText("показан запасной текст")).toBeVisible();
  const fallback = page.getByText(
    "сегодняшний фон спокойный. это развлекательный набросок, не обещание события.",
  );
  await expect(fallback).toBeVisible();
  await expect(fallback).toHaveText(
    "сегодняшний фон спокойный. это развлекательный набросок, не обещание события.",
  );
  await expect(fallback).toHaveCSS("text-transform", "none");
  await expect(page.locator("body")).not.toContainText("TESTTOKEN");
  await expect(page.locator("body")).not.toContainText("initData");
});
