import { useNavigate } from "react-router";

import type { ProfileResponse } from "../api/client";
import { Icon } from "../components/ui/icons";
import { RotatingPhrase } from "../components/ui/RotatingPhrase";
import { text, type TextKey } from "../resources";
import { signEmoji } from "../signEmoji";

type HomePageProps = {
  profile: ProfileResponse;
};

const TILES: { to: string; label: TextKey; emoji: string }[] = [
  { to: "/reading/day", label: "ui.reading.day", emoji: "☀️" },
  { to: "/reading/week", label: "ui.reading.week", emoji: "📅" },
  { to: "/reading/advice", label: "ui.reading.advice", emoji: "💡" },
  { to: "/reading/moon", label: "ui.reading.moon", emoji: "🌙" },
  { to: "/reading/compatibility", label: "ui.reading.compatibility", emoji: "🤝" },
  { to: "/chart", label: "ui.chart.title", emoji: "🪐" },
  { to: "/history", label: "ui.reading.history", emoji: "📜" },
  { to: "/favorites", label: "ui.reading.favorites", emoji: "⭐" },
  { to: "/related", label: "ui.reading.related", emoji: "👥" },
  { to: "/referral", label: "ui.reading.referral", emoji: "🔗" },
  { to: "/settings", label: "ui.settings.title", emoji: "⚙️" },
  { to: "/premium", label: "ui.premium.title", emoji: "✨" },
  { to: "/help", label: "ui.help.title", emoji: "❓" },
  { to: "/terms", label: "ui.terms.title", emoji: "📋" },
  { to: "/paysupport", label: "ui.paysupport.title", emoji: "💬" },
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
          <span
            className="plan-mark"
            role="img"
            aria-label={text(profile.is_premium ? "ui.home.plan_premium" : "ui.home.plan_free")}
          >
            <span className="emoji" aria-hidden="true">
              {profile.is_premium ? "✨" : "🆓"}
            </span>
          </span>
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

function profileLetter(name: string | null): string | null {
  const trimmed = name?.trim() ?? "";
  if (trimmed.length === 0) {
    return null;
  }
  const [letter] = Array.from(trimmed);
  return letter ?? null;
}
