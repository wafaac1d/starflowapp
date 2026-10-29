import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import { getFavorable, type FavorableDay } from "../api/client";
import { queryKeys } from "../api/keys";
import { Button } from "../shared/ui/Button/Button";
import { Field } from "../shared/ui/Field/Field";
import { Icon } from "../shared/ui/Icon/Icon";
import { MonthGrid } from "../shared/ui/MonthGrid/MonthGrid";
import { Screen } from "../shared/ui/Screen/Screen";
import { Skeleton } from "../shared/ui/Skeleton/Skeleton";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

const PRESETS = [
  { id: "meeting", title: "Встреча", suit: "Подходит для встречи" },
  { id: "trip", title: "Поездка", suit: "Подходит для поездки" },
  { id: "purchase", title: "Покупка", suit: "Подходит для покупки" },
] as const;

type EventId = (typeof PRESETS)[number]["id"] | "custom";

export function FavorableDateScreen() {
  const navigate = useNavigate();
  const today = new Date();
  const [event, setEvent] = useState<EventId>("meeting");
  const [draft, setDraft] = useState("");
  const [committed, setCommitted] = useState("");
  const [cursor, setCursor] = useState({ year: today.getFullYear(), month: today.getMonth() + 1 });
  const [selected, setSelected] = useState("");
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
  const ready = event !== "custom" || custom.length >= 2;
  const favorable = useQuery({
    queryKey: queryKeys.favorable(month, event, custom),
    queryFn: () => getFavorable(month, event, custom),
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
      </div>
    </Screen>
  );
}

function suitFor(event: EventId, custom: string): string {
  const preset = PRESETS.find((item) => item.id === event);
  if (preset !== undefined) {
    return preset.suit;
  }
  return `Подходит для ${custom}`;
}

function presetTitle(event: EventId): string {
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
