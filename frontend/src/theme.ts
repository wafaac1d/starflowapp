export type ThemeChoice = "light" | "dark" | "telegram";

const KEY = "starflow-theme";

export function resolveTheme(
  choice: ThemeChoice,
  telegramScheme: "light" | "dark" | null,
  prefersDark: boolean,
): "light" | "dark" {
  if (choice === "light" || choice === "dark") {
    return choice;
  }
  if (telegramScheme === "light" || telegramScheme === "dark") {
    return telegramScheme;
  }
  return prefersDark ? "dark" : "light";
}

export function readThemeChoice(): ThemeChoice {
  try {
    const stored = localStorage.getItem(KEY);
    if (stored === "light" || stored === "dark" || stored === "telegram") {
      return stored;
    }
  } catch {
    return "telegram";
  }
  return "telegram";
}

let detach: (() => void) | null = null;

export function applyTheme(choice: ThemeChoice): void {
  detach?.();
  detach = null;
  try {
    localStorage.setItem(KEY, choice);
  } catch {
    /* storage can be unavailable in a private webview */
  }
  const paint = () => {
    const scheme = window.Telegram?.WebApp?.colorScheme;
    const telegram = scheme === "dark" || scheme === "light" ? scheme : null;
    const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ?? true;
    document.documentElement.dataset.theme = resolveTheme(choice, telegram, prefersDark);
    document.documentElement.dataset.themeChoice = choice;
  };
  paint();
  if (choice !== "telegram") {
    return;
  }
  const media = window.matchMedia?.("(prefers-color-scheme: dark)");
  const raw = window.Telegram?.WebApp;
  media?.addEventListener("change", paint);
  raw?.onEvent?.("themeChanged", paint);
  detach = () => {
    media?.removeEventListener("change", paint);
    raw?.offEvent?.("themeChanged", paint);
  };
}

export function bindViewportChrome(): void {
  const apply = () => {
    const viewport = window.visualViewport;
    if (viewport === null || viewport === undefined) {
      return;
    }
    const covered = Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop);
    const keyboard = covered > 80;
    document.documentElement.dataset.keyboard = keyboard ? "open" : "closed";
    document.documentElement.style.setProperty("--keyboard-inset", `${covered}px`);
  };
  apply();
  window.visualViewport?.addEventListener("resize", apply);
  window.visualViewport?.addEventListener("scroll", apply);
  document.addEventListener("focusin", (event) => {
    const target = event.target;
    if (target instanceof HTMLElement && document.documentElement.dataset.keyboard === "open") {
      target.scrollIntoView({ block: "center" });
    }
  });
}
