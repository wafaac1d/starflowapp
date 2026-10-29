import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { getRetro, type ProfileResponse } from "../api/client";
import { queryKeys } from "../api/keys";
import { STAR_SILENCE, useReading } from "../readingWait";
import { Button } from "../shared/ui/Button/Button";
import { Icon } from "../shared/ui/Icon/Icon";
import { Screen } from "../shared/ui/Screen/Screen";
import { Skeleton } from "../shared/ui/Skeleton/Skeleton";
import { formatRuDate, greeting } from "./format";
import styles from "./screens.module.css";
import { TopUpDialog } from "./TopUpDialog";
import { useTopicDetail } from "./topicDetail";

const CATEGORIES = [
  { id: "love", label: "Любовь", icon: "cat_love" as const },
  { id: "work", label: "Работа", icon: "cat_work" as const },
  { id: "health", label: "Здоровье", icon: "cat_health" as const },
  { id: "finance", label: "Финансы", icon: "cat_finance" as const },
];

const PRACTICES = [
  {
    title: "Совместимость",
    lead: "Связь между двумя людьми",
    image: "/compatibility/compatibility_256.png",
    to: "/compatibility",
  },
  {
    title: "Натальная карта",
    lead: "Солнце, Луна и асцендент",
    image: "/natal_chart/natal_chart_256.png",
    to: "/natal",
  },
  {
    title: "Ретроградные планеты",
    lead: "Периоды и рекомендации",
    image: "/retrograde_planets/retrograde_planets_256.png",
    to: "/retro",
  },
  {
    title: "Аффирмации",
    lead: "Настройтесь на свой ритм",
    image: "/affirmations/affirmations_256.png",
    to: "/affirmations",
  },
  {
    title: "Благоприятная дата",
    lead: "Подберите день для события",
    image: "/favorable_date/favorable_date_256.png",
    to: "/favorable",
  },
] as const;

function isoToday(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function periodBadge(count: number): string | null {
  if (count <= 0) {
    return null;
  }
  const mod10 = count % 10;
  const mod100 = count % 100;
  let word = "периодов";
  if (mod10 === 1 && mod100 !== 11) {
    word = "период";
  } else if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    word = "периода";
  }
  return `${count} ${word}`;
}

export function TodayScreen({ profile }: { profile: ProfileResponse }) {
  const navigate = useNavigate();
  const [topUp, setTopUp] = useState(false);
  const balance = profile.star_balance ?? 0;
  const now = new Date();
  const reading = useReading("day");
  const waiting = reading.face.phase === "loading";
  const title = reading.face.phase === "ready" ? reading.face.title : STAR_SILENCE;
  const topics = useTopicDetail(profile.is_premium);
  const retro = useQuery({
    queryKey: queryKeys.retro,
    queryFn: () => getRetro(),
  });
  const today = isoToday();
  const currentPeriods = (Array.isArray(retro.data) ? retro.data : []).filter(
    (period) => period.start <= today && today <= period.end,
  ).length;
  const retroBadge = periodBadge(currentPeriods);
  const openForecast = () => {
    void navigate("/forecast");
  };
  return (
    <Screen tab="today">
      <div className={styles.fill}>
        <div className={styles.topRow}>
          <div className={styles.headCopy}>
            <p className={styles.kicker}>{greeting(now)}</p>
            <h1 className={styles.name}>{profile.display_name ?? ""}</h1>
            <p className={styles.kicker}>{formatRuDate(now)}</p>
          </div>
          <button
            type="button"
            className={styles.balanceButton}
            aria-label={profile.is_premium ? `Баланс unlim/${balance}` : `Баланс ${balance}`}
            onClick={() => {
              setTopUp(true);
            }}
          >
            {profile.is_premium ? (
              <span className={styles.balanceFace}><span>unlim</span><span className={styles.balanceRest}>/{balance}</span></span>
            ) : (
              balance
            )}
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
        <section className={styles.practices} aria-labelledby="practices-title">
          <h2 id="practices-title" className={styles.practiceHeading}>
            Ваши астропрактики
          </h2>
          {PRACTICES.map((item) => {
            const badge = item.to === "/retro" ? retroBadge : null;
            return (
              <button
                key={item.to}
                type="button"
                className={styles.practice}
                onClick={() => {
                  void navigate(item.to);
                }}
              >
                <img className={styles.practiceIcon} src={item.image} alt="" />
                <span className={styles.practiceCopy}>
                  <span className={styles.practiceTitle}>{item.title}</span>
                  <span className={styles.practiceLead}>{item.lead}</span>
                  {badge !== null ? <span className={styles.practiceBadge}>{badge}</span> : null}
                </span>
                <Icon name="chevron_right" size={18} />
              </button>
            );
          })}
        </section>
      </div>
      {topics.dialog}
      {topUp ? <TopUpDialog balance={balance} onClose={() => setTopUp(false)} /> : null}
    </Screen>
  );
}
