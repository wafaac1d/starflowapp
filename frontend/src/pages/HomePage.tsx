import { useNavigate } from "react-router";

import type { ProfileResponse } from "../api/client";
import { Icon } from "../components/ui/icons";
import { formatText, homeCopy, text, type TextKey } from "../resources";

type HomePageProps = {
  profile: ProfileResponse;
};

const TILES: { to: string; label: TextKey; icon: "chart" | "settings" | "premium" | "help" | "terms" | "support" }[] =
  [
    { to: "/chart", label: "ui.chart.title", icon: "chart" },
    { to: "/settings", label: "ui.settings.title", icon: "settings" },
    { to: "/premium", label: "ui.premium.title", icon: "premium" },
    { to: "/help", label: "ui.help.title", icon: "help" },
    { to: "/terms", label: "ui.terms.title", icon: "terms" },
    { to: "/paysupport", label: "ui.paysupport.title", icon: "support" },
  ];

export function HomePage({ profile }: HomePageProps) {
  const navigate = useNavigate();
  const sign =
    profile.calendar_sign === null
      ? homeCopy.title
      : profile.display_name
        ? formatText("ui.onboarding.sign_named", { name: profile.display_name })
        : text("ui.onboarding.sign_title");
  const letter = profileLetter(profile.display_name);

  return (
    <main className="shell">
      <header className="home-top">
        <div>
          <h1>{sign}</h1>
          {profile.calendar_sign !== null ? <p className="lead">{profile.calendar_sign}</p> : null}
          <p className="lead">{homeCopy.lead}</p>
        </div>
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
      </header>
      <p className="disclaimer">{homeCopy.disclaimer}</p>
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
            <Icon name={tile.icon} />
            <span>{text(tile.label)}</span>
          </button>
        ))}
      </div>
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
