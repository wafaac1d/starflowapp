import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import { ApiRequestError, getFavorable, getFavorableStatus, spendStars, type FavorableDay } from "../api/client";
import { queryKeys } from "../api/keys";
import { Button } from "../shared/ui/Button/Button";
import { Field } from "../shared/ui/Field/Field";
import { Icon } from "../shared/ui/Icon/Icon";
import { MonthGrid } from "../shared/ui/MonthGrid/MonthGrid";
import { Screen } from "../shared/ui/Screen/Screen";
import { Skeleton } from "../shared/ui/Skeleton/Skeleton";
import { StarPrice } from "../shared/ui/StarPrice/StarPrice";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import { holdStarBalance, writeStarBalance } from "../starBalance";
import { FAVORABLE_STARS } from "../stars";
import { TopUpDialog } from "./TopUpDialog";
import styles from "./screens.module.css";

const PRESETS = [
  { id: "meeting", title: "Встреча", suit: "Подходит для встречи" },
  { id: "trip", title: "Поездка", suit: "Подходит для поездки" },
  { id: "purchase", title: "Покупка", suit: "Подходит для покупки" },
] as const;

type EventId = (typeof PRESETS)[number]["id"] | "custom";

export function FavorableDateScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [topUp, setTopUp] = useState(false);
  const today = new Date();
  const statusQuery = useQuery({
    queryKey: queryKeys.favorableStatus,
    queryFn: () => getFavorableStatus(),
  });
  const isPremium = statusQuery.data?.is_premium === true;
  const initialEvent = useMemo<EventId | null>(() => {
    if (statusQuery.data?.chosen_event) {
      return statusQuery.data.chosen_event as EventId;
    }
    if (isPremium) {
      return "meeting";
    }
    return null;
  }, [statusQuery.data, isPremium]);

  const [event, setEvent] = useState<EventId | null>(null);
  const [draft, setDraft] = useState("");
  const [committed, setCommitted] = useState("");
  const [cursor, setCursor] = useState({ year: today.getFullYear(), month: today.getMonth() + 1 });
  const [selected, setSelected] = useState("");

  useEffect(() => {
    if (event === null && initialEvent !== null) {
      setEvent(initialEvent);
      if (initialEvent === "custom" && statusQuery.data?.chosen_custom) {
        setDraft(statusQuery.data.chosen_custom);
        setCommitted(statusQuery.data.chosen_custom);
      }
    }
  }, [initialEvent, event, statusQuery.data]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setCommitted(draft.trim());
    }, 400);
    return () => {
      window.clearTimeout(handle);
    };
  }, [draft]);

  const month = `${cursor.year}-${String(cursor.month).padStart(2, "0")}`;
  const custom = event === "custom" ? committed : "";
  const ready = event !== null && (event !== "custom" || custom.length >= 2);
  const activeEvent = event ?? "meeting";
  const favorable = useQuery({
    queryKey: queryKeys.favorable(month, activeEvent, custom),
    queryFn: () => getFavorable(month, activeEvent, custom),
    enabled: ready,
  });
  const days = useMemo(
    () => (favorable.data?.status === "ready" ? favorable.data.days : []),
    [favorable.data],
  );
  useEffect(() => {
    const inThisMonth = selected.startsWith(month);
    if (days.length === 0 || (inThisMonth && selected !== "")) {
      return;
    }
    const todayIso = isoToday();
    const pick = days.find((day) => day.date >= todayIso) ?? days[0];
    if (pick !== undefined) {
      setSelected(pick.date);
    }
  }, [days, month, selected]);
  const marks = new Set(days.map((day) => day.date));
  const chosen = days.find((day) => day.date === selected);
  const failed = favorable.isError || favorable.data?.status === "unavailable";
  const isLocked = favorable.data?.access === "locked";
  const isPreview = favorable.data?.access === "preview" && (favorable.data.price ?? 0) > 0;
  const locked = isLocked || isPreview;
  const price = favorable.data?.price ?? FAVORABLE_STARS;
  const buy = useMutation({
    mutationFn: () =>
      event !== null
        ? spendStars({ feature: "favorable", month, event, custom })
        : Promise.reject(new Error("no event selected")),
    onMutate: () => holdStarBalance(queryClient, price),
    onSuccess: async (ticket, _variables, restore) => {
      if (ticket.charged) {
        writeStarBalance(queryClient, ticket.balance);
      } else {
        restore?.();
      }
      if (event !== null) {
        await queryClient.invalidateQueries({
          queryKey: queryKeys.favorable(month, event, custom),
        });
      }
      await queryClient.invalidateQueries({ queryKey: queryKeys.favorableStatus });
    },
    onError: (error, _variables, restore) => {
      restore?.();
      if (error instanceof ApiRequestError && error.status === 402) {
        setTopUp(true);
      }
    },
  });
  return (
    <Screen>
      <TopBar
        title="Благоприятная дата"
        back
        onBack={() => {
          void navigate("/");
        }}
      />
      <div className={styles.favorableBody}>
        <p className={styles.favorableQuestion}>Для какого события ищем день?</p>
        <div className={styles.events} role="group" aria-label="Событие">
          {PRESETS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={event === item.id ? styles.eventOn : styles.event}
              aria-pressed={event === item.id}
              onClick={() => {
                setEvent(item.id);
              }}
            >
              {item.title}
            </button>
          ))}
          <button
            type="button"
            className={event === "custom" ? styles.eventOn : styles.event}
            aria-pressed={event === "custom"}
            onClick={() => {
              setEvent("custom");
            }}
          >
            Свой вариант
          </button>
        </div>
        {event === "custom" ? (
          <Field label="Своё событие" value={draft} chevron={false} onChange={setDraft} />
        ) : null}
        {event === null ? (
          <article className={styles.favorableCard}>
            <p className={styles.favorableNote}>
              Выберите категорию выше, чтобы рассчитать ближайший благоприятный день по вашему знаку зодиака, дате и времени рождения. Бесплатно доступен один расчёт в день.
            </p>
          </article>
        ) : (
          <>
            <MonthGrid
              year={cursor.year}
              month={cursor.month}
              selected={selected}
              marks={marks}
              onSelect={setSelected}
              onPrevious={() => {
                setCursor((current) => shift(current, -1));
              }}
              onNext={() => {
                setCursor((current) => shift(current, 1));
              }}
            />
            <p className={styles.favorableLegend}>
              <span className={styles.favorableDot} />
              Благоприятный день
            </p>
            {favorable.isPending && ready ? <Skeleton lines={3} /> : null}
            {failed ? <p role="status">Не удалось подобрать дни.</p> : null}
            {isLocked ? (
              <article className={styles.favorableCard}>
                <div className={styles.favorableHead}>
                  <h2>Категория недоступна бесплатно</h2>
                  {favorable.data?.free_chosen_label ? (
                    <p className={styles.favorableSuit}>Выбрано: {favorable.data.free_chosen_label}</p>
                  ) : null}
                </div>
                <p className={styles.favorableNote}>
                  {favorable.data?.free_chosen_label
                    ? `Бесплатно в день доступен просмотр только одной категории. Сегодня вы уже выбрали «${favorable.data.free_chosen_label}».`
                    : "Бесплатно в день доступен просмотр только одной категории."}{" "}
                  Полный календарь месяца для события «{presetTitle(event)}» доступен за{" "}
                  <StarPrice amount={price} /> звёзд или с Premium.
                </p>
              </article>
            ) : null}
            {chosen !== undefined ? (
              <article className={styles.favorableCard}>
                <div className={styles.favorableHead}>
                  <h2>{dayTitle(chosen.date)}</h2>
                  <p className={styles.favorableSuit}>{suitFor(event, custom)}</p>
                </div>
                <p className={styles.favorableTime}>
                  <Icon name="clock" size={18} />
                  Лучшее время · {chosen.start}–{chosen.end}
                </p>
                <p className={styles.favorableNote}>{chosen.note}</p>
              </article>
            ) : null}
            {!favorable.isPending &&
            ready &&
            !failed &&
            !isLocked &&
            chosen === undefined &&
            selected.startsWith(month) ? (
              <p className={styles.favorableNote}>Этот день не отмечен.</p>
            ) : null}
            <Button
              icon="date_calendar"
              disabled={chosen === undefined}
              onClick={() => {
                if (chosen !== undefined) {
                  addToCalendar(event === "custom" ? custom : presetTitle(event), chosen);
                }
              }}
            >
              Добавить в календарь
            </Button>
          </>
        )}
        {locked ? (
          <section className={styles.favorableOffer}>
            <p>
              {isLocked
                ? `Полный календарь месяца для этого события стоит `
                : `Ближайший день бесплатно. Полный календарь месяца для этого события стоит `}
              <StarPrice amount={price} /> звёзд. С Premium он без ограничений.
            </p>
            <Button
              loading={buy.isPending}
              onClick={() => {
                buy.mutate();
              }}
            >
              Открыть за <StarPrice amount={price} />
            </Button>
          </section>
        ) : null}
        {topUp ? <TopUpDialog balance={null} onClose={() => setTopUp(false)} /> : null}
      </div>
    </Screen>
  );
}

function suitFor(event: EventId | null, custom: string): string {
  if (event === null) {
    return "";
  }
  const preset = PRESETS.find((item) => item.id === event);
  if (preset !== undefined) {
    return preset.suit;
  }
  return `Подходит для ${custom}`;
}

function presetTitle(event: EventId | null): string {
  if (event === null) {
    return "Событие";
  }
  const preset = PRESETS.find((item) => item.id === event);
  return preset?.title ?? "Событие";
}

function dayTitle(iso: string): string {
  const [year, month, day] = iso.split("-").map((part) => Number(part));
  return new Intl.DateTimeFormat("ru", { day: "numeric", month: "long" }).format(
    new Date(year ?? 2000, (month ?? 1) - 1, day ?? 1),
  );
}

function isoToday(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function shift(current: { year: number; month: number }, delta: number): { year: number; month: number } {
  const index = current.year * 12 + (current.month - 1) + delta;
  const year = Math.floor(index / 12);
  return { year, month: index - year * 12 + 1 };
}

function addToCalendar(title: string, day: FavorableDay): void {
  const stamp = day.date.replaceAll("-", "");
  const start = `${stamp}T${day.start.replace(":", "")}00`;
  const end = `${stamp}T${day.end.replace(":", "")}00`;
  const description = `${day.note} Развлекательный набросок, не обещание события.`;
  const body = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//StarFlow//RU",
    "BEGIN:VEVENT",
    `DTSTART:${start}`,
    `DTEND:${end}`,
    `SUMMARY:${icsText(title)}`,
    `DESCRIPTION:${icsText(description)}`,
    "END:VEVENT",
    "END:VCALENDAR",
  ].join("\r\n");
  const file = new Blob([body], { type: "text/calendar" });
  const url = URL.createObjectURL(file);
  const link = document.createElement("a");
  link.href = url;
  link.download = `starflow-${day.date}.ics`;
  link.click();
  URL.revokeObjectURL(url);
}

function icsText(value: string): string {
  return value.replaceAll("\\", "\\\\").replaceAll("\n", "\\n").replaceAll(",", "\\,").replaceAll(";", "\\;");
}
