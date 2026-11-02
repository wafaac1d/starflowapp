import { useEffect } from "react";
import { useLocation } from "react-router";

export function scrollToTop(): void {
  try {
    if (typeof window !== "undefined" && typeof window.scrollTo === "function") {
      window.scrollTo(0, 0);
    }
  } catch {
    /* jsdom or restricted environments */
  }
  if (typeof document !== "undefined") {
    if (document.documentElement) {
      document.documentElement.scrollTop = 0;
    }
    if (document.body) {
      document.body.scrollTop = 0;
    }
    const root = document.getElementById("root");
    if (root) {
      root.scrollTop = 0;
    }
    const appColumn = document.querySelector(".app-column");
    if (appColumn) {
      appColumn.scrollTop = 0;
    }
  }
}

export function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    scrollToTop();
  }, [pathname]);

  return null;
}
