import { useEffect, useState } from "react";

import { prefersReducedMotion } from "../../motion";
import { text, type TextKey } from "../../resources";

const PHRASES: TextKey[] = [
  "ui.home.phrase_1",
  "ui.home.phrase_2",
  "ui.home.phrase_3",
  "ui.home.phrase_4",
  "ui.home.phrase_5",
  "ui.home.phrase_6",
  "ui.home.phrase_7",
  "ui.home.phrase_8",
  "ui.home.phrase_9",
  "ui.home.phrase_10",
];

const PHRASE_HOLD_MS = 10_000;
const PHRASE_FADE_MS = 1_400;

type RotatingPhraseProps = {
  tone?: "home" | "muted";
};

export function RotatingPhrase({ tone = "home" }: RotatingPhraseProps) {
  const [index, setIndex] = useState(() => Math.floor(Math.random() * PHRASES.length));
  const [previous, setPrevious] = useState<number | null>(null);

  useEffect(() => {
    if (prefersReducedMotion()) {
      return;
    }
    const id = window.setInterval(() => {
      setIndex((current) => {
        setPrevious(current);
        return (current + 1) % PHRASES.length;
      });
    }, PHRASE_HOLD_MS);
    return () => {
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    if (previous === null) {
      return;
    }
    const id = window.setTimeout(() => {
      setPrevious(null);
    }, PHRASE_FADE_MS);
    return () => {
      window.clearTimeout(id);
    };
  }, [previous]);

  const phrase = PHRASES[index] ?? "ui.home.phrase_1";
  const outgoing = previous === null ? null : PHRASES[previous];
  return (
    <p className={tone === "muted" ? "start-phrase" : "home-phrase"} aria-live="polite">
      {outgoing !== null && outgoing !== undefined ? (
        <span className="home-phrase-line" data-phase="out" aria-hidden="true">
          {text(outgoing)}
        </span>
      ) : null}
      <span className="home-phrase-line" data-phase={previous === null ? "steady" : "in"}>
        {text(phrase)}
      </span>
    </p>
  );
}
