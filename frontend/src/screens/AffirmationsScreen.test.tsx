import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AffirmationsScreen } from "./AffirmationsScreen";

const FOR_YOU = {
  category: "for_you",
  label: "Для вас",
  access: "preview",
  price: 20,
  cards: [
    {
      id: "for_you:0",
      category: "for_you",
      text: "«Я доверяю себе и выбираю свой ритм.»",
      bg_image: "/affirmations/affirmation_backgrounds/affirmation_background_01.png",
    },
    {
      id: "for_you:1",
      category: "for_you",
      text: "«Каждый мой шаг приближает меня к гармонии.»",
      bg_image: "/affirmations/affirmation_backgrounds/affirmation_background_02.png",
    },
    {
      id: "for_you:2",
      category: "for_you",
      text: "«Я открываюсь новому дню.»",
      bg_image: "/affirmations/affirmation_backgrounds/affirmation_background_03.png",
    },
  ],
};

const CONFIDENCE = {
  category: "confidence",
  label: "Уверенность",
  access: "preview",
  price: 20,
  cards: [
    {
      id: "confidence:0",
      category: "confidence",
      text: "«Во мне есть всё необходимое.»",
      bg_image: "/affirmations/affirmation_backgrounds/affirmation_background_01.png",
    },
  ],
};

const CALM = {
  category: "calm",
  label: "Спокойствие",
  access: "preview",
  price: 20,
  cards: [
    {
      id: "calm:0",
      category: "calm",
      text: "«Я отпускаю спешку.»",
      bg_image: "/affirmations/affirmation_backgrounds/affirmation_background_01.png",
    },
  ],
};

const NOTICES = {
  local_time: "09:00",
  timezone: "Europe/Moscow",
  day: true,
  moon: true,
  retro: true,
  affirmation: false,
};

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
    vi.restoreAllMocks();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url.includes("/affirmations/status")) {
          return Response.json({
            chosen_category: null,
            chosen_label: null,
            is_premium: false,
          });
        }
        if (url.includes("/affirmations/keeps")) {
          if (method === "POST") {
            return Response.json({
              id: "11111111-1111-1111-1111-111111111111",
              card_id: "for_you:0",
              text: "сохранено",
              category: "for_you",
            });
          }
          if (method === "DELETE") {
            return new Response(null, { status: 204 });
          }
          return Response.json([]);
        }
        if (url.includes("/notifications")) {
          if (method === "PUT") {
            return Response.json(JSON.parse(String(init?.body)));
          }
          return Response.json(NOTICES);
        }
        if (url.includes("category=confidence")) {
          return Response.json(CONFIDENCE);
        }
        if (url.includes("category=calm")) {
          return Response.json(CALM);
        }
        if (url.includes("/affirmations")) {
          return Response.json(FOR_YOU);
        }
        return Response.json({});
      }),
    );
  });

  it("waits for an explicit category before loading cards", async () => {
    renderScreen();
    expect(screen.getByRole("heading", { name: "Аффирмации" })).toBeInTheDocument();
    expect(screen.getByText("Выберите категорию")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Для вас" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByText(/Я доверяю себе/)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Для вас" }));
    expect(await screen.findByText(/Я доверяю себе/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Для вас" })).toHaveAttribute("aria-pressed", "true");
  });

  it("switches category only after the user chooses it", async () => {
    renderScreen();
    await userEvent.click(screen.getByRole("button", { name: "Уверенность" }));
    expect(await screen.findByText(/Во мне есть всё необходимое/)).toBeInTheDocument();
    expect(screen.queryByText(/Я доверяю себе/)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Спокойствие" }));
    expect(await screen.findByText(/Я отпускаю спешку/)).toBeInTheDocument();
  });

  it("advances to the next affirmation from the server cards", async () => {
    renderScreen();
    await userEvent.click(screen.getByRole("button", { name: "Для вас" }));
    expect(await screen.findByText(/Я доверяю себе/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Показать другую аффирмацию" }));
    expect(screen.getByText(/Каждый мой шаг приближает/)).toBeInTheDocument();
  });

  it("saves an affirmation on the server", async () => {
    const fetchMock = vi.mocked(fetch);
    renderScreen();
    await userEvent.click(screen.getByRole("button", { name: "Для вас" }));
    const saveBtn = await screen.findByRole("button", { name: "Сохранить аффирмацию" });
    await userEvent.click(saveBtn);
    expect(
      fetchMock.mock.calls.some(
        (call) => String(call[0]).includes("/affirmations/keeps") && call[1]?.method === "POST",
      ),
    ).toBe(true);
  });

  it("shares the opened affirmation", async () => {
    const shareMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "share", {
      value: shareMock,
      configurable: true,
    });
    renderScreen();
    await userEvent.click(screen.getByRole("button", { name: "Для вас" }));
    await userEvent.click(await screen.findByRole("button", { name: "Поделиться аффирмацией" }));
    expect(shareMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Аффирмация дня",
        text: expect.stringContaining("Я доверяю себе"),
      }),
    );
  });

  it("toggles the affirmation reminder without changing the day digest", async () => {
    const fetchMock = vi.mocked(fetch);
    renderScreen();
    const toggle = await screen.findByRole("switch", { name: "Напоминать каждый день" });
    expect(toggle).not.toBeChecked();
    await userEvent.click(toggle);
    const saved = fetchMock.mock.calls.find(
      (call) => String(call[0]).includes("/notifications") && call[1]?.method === "PUT",
    );
    const body = JSON.parse(String(saved?.[1]?.body)) as { day: boolean; affirmation: boolean };
    expect(body.affirmation).toBe(true);
    expect(body.day).toBe(true);
  });

  it("swipes horizontally across server cards", async () => {
    renderScreen();
    await userEvent.click(screen.getByRole("button", { name: "Для вас" }));
    const cardRegion = await screen.findByRole("region", { name: "Карточка аффирмации" });
    expect(screen.getByText(/Я доверяю себе/)).toBeInTheDocument();
    fireEvent.touchStart(cardRegion, { touches: [{ clientX: 200, clientY: 100 }] });
    fireEvent.touchEnd(cardRegion, { changedTouches: [{ clientX: 100, clientY: 100 }] });
    expect(screen.getByText(/Каждый мой шаг приближает/)).toBeInTheDocument();
  });

  it("shows a locked category and unlocks it with stars", async () => {
    let unlocked = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url.includes("/stars/spends")) {
          unlocked = true;
          return Response.json({ balance: 80, allowed: true, charged: true, price: 20 });
        }
        if (url.includes("/affirmations/status")) {
          return Response.json({
            chosen_category: "for_you",
            chosen_label: "Для вас",
            is_premium: false,
          });
        }
        if (url.includes("/affirmations/keeps")) {
          return Response.json([]);
        }
        if (url.includes("/notifications")) {
          return Response.json(NOTICES);
        }
        if (url.includes("category=confidence")) {
          if (unlocked) {
            return Response.json({ ...CONFIDENCE, access: "full", price: 0 });
          }
          return Response.json({
            category: "confidence",
            label: "Уверенность",
            access: "locked",
            price: 20,
            cards: [],
            free_chosen_label: "Для вас",
          });
        }
        return Response.json({ ...FOR_YOU, cards: FOR_YOU.cards.slice(0, 1) });
      }),
    );

    renderScreen();
    expect(await screen.findByText(/Я доверяю себе/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Уверенность" }));
    expect(await screen.findByRole("heading", { name: "Категория недоступна бесплатно" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Открыть за/ }));
    expect(await screen.findByText(/Во мне есть всё необходимое/)).toBeInTheDocument();
  });
});
