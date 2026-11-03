export type ThemeChoice = "dark";

export function resolveTheme(
  _choice?: string,
  _telegramScheme?: "light" | "dark" | null,
  _prefersDark?: boolean,
): "dark" {
  return "dark";
}

export function readThemeChoice(): ThemeChoice {
  return "dark";
}

export function applyTheme(_choice?: string): void {
  document.documentElement.dataset.theme = "dark";
  document.documentElement.dataset.themeChoice = "dark";
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
