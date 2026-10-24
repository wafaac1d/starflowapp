import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { getReading, startReading, readingKey, type ProfileResponse } from "../api/client";
import { forecastTitle } from "../api/fixtures";
import { queryKeys } from "../api/keys";
import { Button } from "../shared/ui/Button/Button";
import { Icon } from "../shared/ui/Icon/Icon";
import { Screen } from "../shared/ui/Screen/Screen";
import { formatRuDate, greeting } from "./format";
import styles from "./screens.module.css";

const CATEGORIES = [
  { id: "love", label: "Любовь", icon: "cat_love" as const },
  { id: "work", label: "Работа", icon: "cat_work" as const },
  { id: "health", label: "Здоровье", icon: "cat_health" as const },
  { id: "finance", label: "Финансы", icon: "cat_finance" as const },
];

export function TodayScreen({ profile }: { profile: ProfileResponse }) {
  const navigate = useNavigate();
  const now = new Date();
  const reading = useQuery({
    queryKey: queryKeys.reading("day"),
    queryFn: async () => {
      await startReading("day", readingKey());
      return getReading("day");
    },
  });
  const title = reading.data?.title || forecastTitle;
  const openForecast = () => {
    void navigate("/forecast");
  };
  return (
    <Screen tab="today">
      <div className={styles.topRow}>
        <div>
          <p className={styles.kicker}>{greeting(now)}</p>
          <h1 className={styles.name}>{profile.display_name ?? ""}</h1>
          <p className={styles.kicker}>{formatRuDate(now)}</p>
        </div>
        <button
          type="button"
          className={styles.profileButton}
          aria-label="профиль"
          onClick={() => {
            void navigate("/profile");
          }}
        >
          <Icon name="user_circle" size={28} />
        </button>
      </div>
      <img className={styles.hero} src="/illustrations/png/home_moon_orbits.png" alt="" />
      <section className={styles.decision}>
        <button type="button" className={styles.decisionHead} onClick={() => void navigate("/natal")}>
          <Icon name="profile_trait_sparkle" size={22} />
          <span>{title}</span>
          <Icon name="chevron_right" size={18} />
        </button>
        <Button onClick={openForecast}>Открыть прогноз</Button>
      </section>
      <div className={styles.cats}>
        {CATEGORIES.map((item) => (
          <button key={item.id} type="button" className={styles.cat} onClick={openForecast}>
            <Icon name={item.icon} size={28} />
            {item.label}
          </button>
        ))}
      </div>
    </Screen>
  );
}
