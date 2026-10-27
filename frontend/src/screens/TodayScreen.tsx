import { useNavigate } from "react-router";

import type { ProfileResponse } from "../api/client";
import { STAR_SILENCE, useReading } from "../readingWait";
import { Button } from "../shared/ui/Button/Button";
import { Icon } from "../shared/ui/Icon/Icon";
import { Screen } from "../shared/ui/Screen/Screen";
import { Skeleton } from "../shared/ui/Skeleton/Skeleton";
import { formatRuDate, greeting } from "./format";
import styles from "./screens.module.css";
import { useTopicDetail } from "./topicDetail";

const CATEGORIES = [
  { id: "love", label: "Любовь", icon: "cat_love" as const },
  { id: "work", label: "Работа", icon: "cat_work" as const },
  { id: "health", label: "Здоровье", icon: "cat_health" as const },
  { id: "finance", label: "Финансы", icon: "cat_finance" as const },
];

export function TodayScreen({ profile }: { profile: ProfileResponse }) {
  const navigate = useNavigate();
  const now = new Date();
  const reading = useReading("day");
  const waiting = reading.face.phase === "loading";
  const title = reading.face.phase === "ready" ? reading.face.title : STAR_SILENCE;
  const topics = useTopicDetail(profile.is_premium);
  const openForecast = () => {
    void navigate("/forecast");
  };
  return (
    <Screen tab="today">
      <div className={styles.fill}>
        <div className={styles.topRow}>
          <div>
            <p className={styles.kicker}>{greeting(now)}</p>
            <h1 className={styles.name}>{profile.display_name ?? ""}</h1>
            <p className={styles.kicker}>{formatRuDate(now)}</p>
          </div>
          <button
            type="button"
            className={styles.profileButton}
            aria-label="Профиль"
            onClick={() => {
              void navigate("/profile");
            }}
          >
            <Icon name="user_circle" size={28} />
          </button>
        </div>
        <img className={styles.hero} src="/illustrations/png/home_moon_orbits.png" alt="" />
        <section className={styles.decision}>
          <button
            type="button"
            className={styles.decisionHead}
            aria-busy={waiting}
            onClick={() => void navigate("/natal")}
          >
            <Icon name="profile_trait_sparkle" size={22} />
            <span>{waiting ? <Skeleton lines={1} /> : title}</span>
            <span className={styles.decisionChevron}>
              <Icon name="chevron_right" size={18} />
            </span>
          </button>
          <Button onClick={openForecast}>Открыть прогноз</Button>
        </section>
        <div className={styles.cats}>
          {CATEGORIES.map((item) => (
            <button
              key={item.id}
              type="button"
              className={styles.cat}
              onClick={() => {
                topics.open(item.id, item.label);
              }}
            >
              <Icon name={item.icon} size={28} />
              {item.label}
            </button>
          ))}
        </div>
        <div className={styles.todayAction}>
          <Button
            variant="secondary"
            onClick={() => {
              void navigate("/natal");
            }}
          >
            Натальная карта
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              void navigate("/compatibility");
            }}
          >
            Совместимость
          </Button>
        </div>
      </div>
      {topics.dialog}
    </Screen>
  );
}
