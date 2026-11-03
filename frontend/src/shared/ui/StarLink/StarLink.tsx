import { useEffect, useState } from "react";

import styles from "./StarLink.module.css";

export const STAR_LINK_TITLE = "Связь со звёздами";

export const STAR_LINK_LINES = [
  "Слушаем небо",
  "Собираем ритм",
  "Смотрим орбиты",
  "Сверяем карту",
  "Ловим знак",
  "Складываем фон",
  "Держим паузу",
  "Читаем день",
] as const;

const STEP_MS = 2400;

type StarLinkProps = {
  size?: "panel" | "stage";
};

export function StarLink({ size = "panel" }: StarLinkProps) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (motionReduced()) {
      return;
    }
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % STAR_LINK_LINES.length);
    }, STEP_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, []);
  const line = STAR_LINK_LINES[index] ?? "Слушаем небо";
  return (
    <div className={size === "stage" ? styles.stage : styles.panel}>
      <img className={styles.image} src="/starflow_loader_hd.gif" alt="" />
      <p className={styles.title} role="status">
        {STAR_LINK_TITLE}
      </p>
      <p className={styles.line}>{line}</p>
    </div>
  );
}

function motionReduced(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}
