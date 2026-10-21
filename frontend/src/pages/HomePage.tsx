import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import type { ProfileResponse } from "../api/client";
import { Icon } from "../components/ui/icons";
import { prefersReducedMotion } from "../motion";
import { text, type TextKey } from "../resources";
import { signEmoji } from "../signEmoji";

type HomePageProps = {
  profile: ProfileResponse;
};

const TILES: { to: string; label: TextKey; emoji: string }[] = [
  { to: "/chart", label: "ui.chart.title", emoji: "🪐" },
  { to: "/settings", label: "ui.settings.title", emoji: "⚙️" },
  { to: "/premium", label: "ui.premium.title", emoji: "✨" },
  { to: "/help", label: "ui.help.title", emoji: "❓" },
  { to: "/terms", label: "ui.terms.title", emoji: "📄" },
  { to: "/paysupport", label: "ui.paysupport.title", emoji: "💳" },
];

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

export function HomePage({ profile }: HomePageProps) {
  const navigate = useNavigate();
  const letter = profileLetter(profile.display_name);
  const emoji = signEmoji(profile.calendar_sign);

  return (
    <main className="shell screen-fill">
      <header className="home-top">
        <div className="profile-tray" data-sign={emoji !== null}>
          {emoji !== null && profile.calendar_sign !== null ? (
            <span className="sign-mark" role="img" aria-label={profile.calendar_sign}>
              <span className="emoji" aria-hidden="true">
                {emoji}
              </span>
            </span>
          ) : null}
          <button
            type="button"
            className="profile-chip"
            aria-label={text("ui.profile.title")}
            onClick={() => {
              void navigate("/profile");
            }}
          >
            {letter === null ? <Icon name="person" /> : letter}
          </button>
        </div>
      </header>
      <RotatingPhrase />
      <div className="tile-grid">
        {TILES.map((tile) => (
          <button
            key={tile.to}
            type="button"
            className="tile"
            onClick={() => {
              void navigate(tile.to);
            }}
          >
            <span className="emoji" aria-hidden="true">
              {tile.emoji}
            </span>
            <span>{text(tile.label)}</span>
          </button>
        ))}
      </div>
      <p className="home-note">{text("ui.home.disclaimer")}</p>
    </main>
  );
}

function RotatingPhrase() {
  const [index, setIndex] = useState(() => Math.floor(Math.random() * PHRASES.length));
  const [shown, setShown] = useState(true);

  useEffect(() => {
    if (prefersReducedMotion()) {
      return;
    }
    let fadeTimer = 0;
    const id = window.setInterval(() => {
      setShown(false);
      fadeTimer = window.setTimeout(() => {
        setIndex((current) => (current + 1) % PHRASES.length);
        setShown(true);
      }, 450);
    }, 3800);
    return () => {
      window.clearInterval(id);
      window.clearTimeout(fadeTimer);
    };
  }, []);

  const phrase = PHRASES[index] ?? "ui.home.phrase_1";
  return (
    <p className="home-phrase" data-shown={shown} aria-live="polite">
      {text(phrase)}
    </p>
  );
}

function profileLetter(name: string | null): string | null {
  const trimmed = name?.trim() ?? "";
  if (trimmed.length === 0) {
    return null;
  }
  const [letter] = Array.from(trimmed);
  return letter ?? null;
}
