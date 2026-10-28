import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { getNotifications, getRetro, saveNotifications, type RetroPeriod } from "../api/client";
import { queryKeys } from "../api/keys";
import { Button } from "../shared/ui/Button/Button";
import { ErrorState } from "../shared/ui/ErrorState/ErrorState";
import { Screen } from "../shared/ui/Screen/Screen";
import { Skeleton } from "../shared/ui/Skeleton/Skeleton";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

const FILTERS = [
  { id: "now", label: "Сейчас" },
  { id: "soon", label: "Скоро" },
  { id: "all", label: "Все" },
] as const;

type FilterId = (typeof FILTERS)[number]["id"];

const PLANETS: Record<string, { title: string; image: string }> = {
  меркурий: { title: "Меркурий", image: "/planets/mercury_256.png" },
  венера: { title: "Венера", image: "/planets/venus_256.png" },
  марс: { title: "Марс", image: "/planets/mars_256.png" },
  юпитер: { title: "Юпитер", image: "/planets/jupiter_256.png" },
  сатурн: { title: "Сатурн", image: "/planets/saturn_256.png" },
  уран: { title: "Уран", image: "/planets/uranus_256.png" },
  нептун: { title: "Нептун", image: "/planets/neptune_256.png" },
  плутон: { title: "Плутон", image: "/planets/pluto_256.png" },
};

const ORDER = Object.keys(PLANETS);

const MONTHS_SHORT = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
const MONTHS_FULL = [
  "января",
  "февраля",
  "марта",
  "апреля",
  "мая",
  "июня",
  "июля",
  "августа",
  "сентября",
  "октября",
  "ноября",
  "декабря",
];

function parseIso(value: string): Date {
  const [year, month, day] = value.split("-");
  return new Date(Number(year), Number(month) - 1, Number(day));
}

function isoToday(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function monthAt(list: readonly string[], date: Date): string {
  return list[date.getMonth()] ?? "";
}

function shortDate(value: string): string {
  const date = parseIso(value);
  return `${date.getDate()} ${monthAt(MONTHS_SHORT, date)}`;
}

function rangeLabel(start: string, end: string): string {
  const opening = parseIso(start);
  const closing = parseIso(end);
  if (opening.getMonth() === closing.getMonth() && opening.getFullYear() === closing.getFullYear()) {
    return `${opening.getDate()}–${closing.getDate()} ${monthAt(MONTHS_FULL, opening)}`;
  }
  return `${opening.getDate()} ${monthAt(MONTHS_FULL, opening)} — ${closing.getDate()} ${monthAt(MONTHS_FULL, closing)}`;
}

function isCurrent(period: RetroPeriod, today: string): boolean {
  return period.start <= today && today <= period.end;
}

function progress(period: RetroPeriod, today: string): number {
  const opening = parseIso(period.start).getTime();
  const closing = parseIso(period.end).getTime();
  if (closing <= opening) {
    return 0;
  }
  const cursor = parseIso(today).getTime();
  return Math.min(1, Math.max(0, (cursor - opening) / (closing - opening)));
}

function visible(periods: RetroPeriod[], filter: FilterId, today: string): RetroPeriod[] {
  const picked = periods.filter((period) => {
    const current = isCurrent(period, today);
    if (filter === "now") {
      return current;
    }
    if (filter === "soon") {
      return period.start > today;
    }
    return current || period.start > today;
  });
  return [...picked].sort((left, right) => {
    const leftOrder = ORDER.indexOf(left.planet);
    const rightOrder = ORDER.indexOf(right.planet);
    if (leftOrder !== rightOrder) {
      return leftOrder - rightOrder;
    }
    if (left.start < right.start) {
      return -1;
    }
    if (left.start > right.start) {
      return 1;
    }
    return 0;
  });
}

export function RetroScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<FilterId>("now");
  const today = isoToday();
  const periods = useQuery({
    queryKey: queryKeys.retro,
    queryFn: () => getRetro(),
  });
  const notes = useQuery({
    queryKey: queryKeys.notifications,
    queryFn: () => getNotifications(),
  });
  const remind = useMutation({
    mutationFn: async () => {
      const current = notes.data ?? (await getNotifications());
      return saveNotifications({ ...current, retro: true });
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.notifications, saved);
    },
  });
  const armed = notes.data?.retro === true || remind.isSuccess;
  const shown = visible(periods.data ?? [], filter, today);
  return (
    <Screen>
      <TopBar
        title="Ретроградные планеты"
        back
        onBack={() => {
          void navigate("/");
        }}
      />
      <div className={styles.fill}>
        <img className={styles.orbits} src="/illustrations/orbits_1200.png" alt="" />
        <div className={styles.filters} role="tablist" aria-label="Период">
          {FILTERS.map((option) => {
            const selected = filter === option.id;
            return (
              <button
                key={option.id}
                type="button"
                role="tab"
                aria-selected={selected}
                className={selected ? styles.filterOn : styles.filterOff}
                onClick={() => {
                  setFilter(option.id);
                }}
              >
                {option.label}
              </button>
            );
          })}
        </div>
        {periods.isPending ? <Skeleton lines={3} /> : null}
        {periods.isError ? (
          <ErrorState message="Не удалось открыть ретроградные планеты" onRetry={() => void periods.refetch()} />
        ) : null}
        {periods.isSuccess && shown.length === 0 ? (
          <p className={styles.kicker}>В этом разделе периодов нет.</p>
        ) : null}
        {periods.isSuccess
          ? shown.map((period) => {
              const art = PLANETS[period.planet];
              if (art === undefined) {
                return null;
              }
              const current = isCurrent(period, today);
              const ratio = Math.round(progress(period, today) * 100);
              return (
                <article key={`${period.planet}-${period.start}`} className={styles.retroCard}>
                  <div className={styles.retroHead}>
                    <img className={styles.glyph} src={art.image} alt="" />
                    <div className={styles.retroCopy}>
                      <div className={styles.retroTitleRow}>
                        <h2 className={styles.retroTitle}>{art.title}</h2>
                        {current ? <span className={styles.retroBadge}>Ретроградный</span> : null}
                      </div>
                      <p className={styles.retroDates}>{rangeLabel(period.start, period.end)}</p>
                    </div>
                    <img className={styles.chevron} src="/planets/ui/chevron_right_256.png" alt="" />
                  </div>
                  <div
                    className={styles.bar}
                    role="progressbar"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={ratio}
                    aria-label={`${art.title}, ${shortDate(period.start)} — ${shortDate(period.end)}`}
                  >
                    <span className={styles.barFill} style={{ width: `${ratio}%` }} />
                  </div>
                  <div className={styles.barLabels}>
                    <span>{shortDate(period.start)}</span>
                    <span>{shortDate(period.end)}</span>
                  </div>
                </article>
              );
            })
          : null}
        <section className={styles.retroNote}>
          <div className={styles.retroTitleRow}>
            <img className={styles.noteIcon} src="/planets/ui/info_256.png" alt="" />
            <h2 className={styles.retroTitle}>На что обратить внимание</h2>
          </div>
          <ul className={styles.noteList}>
            <li>Перепроверяйте договорённости</li>
            <li>Оставляйте время на паузы</li>
          </ul>
        </section>
        <div className={styles.retroRemind}>
          <Button
            disabled={armed || remind.isPending}
            onClick={() => {
              remind.mutate();
            }}
          >
            <span className={styles.bell} aria-hidden="true" />
            {armed ? "Напоминание включено" : "Напомнить о периоде"}
          </Button>
          {remind.isError ? <p className={styles.kicker}>Не удалось включить напоминание.</p> : null}
        </div>
      </div>
    </Screen>
  );
}
