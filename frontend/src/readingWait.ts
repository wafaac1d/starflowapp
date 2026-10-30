import { useQuery } from "@tanstack/react-query";
import { useRef } from "react";

import {
  getReading,
  readingKey,
  startReading,
  type ReadingQuery,
  type ReadingResponse,
} from "./api/client";
import { queryKeys } from "./api/keys";

export const STAR_SILENCE = "Не удалось связаться со звёздами";

const POLL_MS = 700;

const DATE_RE =
  /(?:^|\s)\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}(?:\s*года|\s*г\.?)?|(?:\b|\s)\d{1,2}\.\d{1,2}\.\d{4}(?:\b|\s)|(?:\b|\s)\d{4}-\d{2}-\d{2}(?:\b|\s)/gi;

const GENERIC_PREFIX_RE =
  /^(?:фон дня|прогноз дня|прогноз на день|прогноз|сегодня|фон)\s*[:\-–—]?\s*/i;

export const GENERAL_DAILY_TITLES = [
  "День для ясных решений",
  "Спокойный ритм и фокус",
  "Время гармонии и баланса",
  "Уверенный импульс для дел",
  "Внутренний баланс и ясность",
  "Благоприятный день для планов",
  "Гармоничный ритм и вдохновение",
] as const;

export function defaultDailyTitle(day?: Date | string | null): string {
  let index = 0;
  if (day instanceof Date) {
    index = day.getDate();
  } else if (typeof day === "string" && day.length >= 10) {
    const num = Number.parseInt(day.slice(8, 10), 10);
    if (!Number.isNaN(num)) {
      index = num;
    }
  } else {
    index = new Date().getDate();
  }
  return GENERAL_DAILY_TITLES[index % GENERAL_DAILY_TITLES.length] ?? GENERAL_DAILY_TITLES[0];
}

export function cleanForecastTitle(
  title: string | null | undefined,
  day?: Date | string | null,
): string {
  if (!title) {
    return defaultDailyTitle(day);
  }
  let clean = title
    .replace(DATE_RE, "")
    .replace(/\s+/g, " ")
    .trim();
  clean = clean.replace(GENERIC_PREFIX_RE, "").trim();
  clean = clean.replace(/[:\-–—\s]+$/, "").replace(/^[:\-–—\s]+/, "").trim();
  const words = clean.split(/\s+/).filter(Boolean);
  if (words.length < 2 || words.length > 7) {
    return defaultDailyTitle(day);
  }
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

export type ReadingFace =
  | { phase: "loading" }
  | { phase: "ready"; title: string; body: string; historyId: string | null }
  | { phase: "premium" }
  | { phase: "stars"; body: string }
  | { phase: "blocked"; body: string }
  | { phase: "miss" };

export function readingFace(
  data: ReadingResponse | undefined,
  waiting: boolean,
  failed: boolean,
): ReadingFace {
  if (waiting) {
    return { phase: "loading" };
  }
  if (failed || data === undefined) {
    return { phase: "miss" };
  }
  if (data.status === "premium") {
    return { phase: "premium" };
  }
  if (data.status === "stars") {
    return { phase: "stars", body: data.body ?? "На балансе не хватает звёзд." };
  }
  if (data.status === "blocked" || data.status === "limit") {
    return { phase: "blocked", body: data.body ?? STAR_SILENCE };
  }
  if (data.status === "ready" && data.body != null && data.body !== "") {
    const rawTitle = data.title != null && data.title !== "" ? data.title : data.body;
    const title = cleanForecastTitle(rawTitle);
    return { phase: "ready", title, body: data.body, historyId: data.history_id };
  }
  return { phase: "miss" };
}

export function useReading(kind: string, query: ReadingQuery = {}, enabled = true) {
  const keys = useRef<Record<string, string>>({});
  const scope = [
    kind,
    query.topic ?? "",
    query.month ?? "",
    query.relatedId ?? "",
    query.leftSign ?? "",
    query.rightSign ?? "",
  ].join("|");
  if (keys.current[scope] === undefined) {
    keys.current[scope] = readingKey();
  }
  const idempotency = keys.current[scope] ?? readingKey();
  const posted = useQuery({
    queryKey: [
      ...queryKeys.reading(kind),
      "start",
      query.topic ?? "",
      query.month ?? "",
      query.relatedId ?? "",
      query.leftSign ?? "",
      query.rightSign ?? "",
    ],
    queryFn: () => startReading(kind, idempotency, fetch, query),
    enabled,
    retry: false,
  });
  const open = posted.data?.status === "pending" || posted.data?.status === "idle";
  const followed = useQuery({
    queryKey: [
      ...queryKeys.reading(kind),
      "current",
      query.topic ?? "",
      query.month ?? "",
      query.relatedId ?? "",
      query.leftSign ?? "",
      query.rightSign ?? "",
    ],
    queryFn: () => getReading(kind, fetch, query),
    enabled: enabled && open,
    retry: false,
    refetchInterval: (state) => {
      const status = state.state.data?.status;
      if (status === "pending" || status === "idle" || status === undefined) {
        return POLL_MS;
      }
      return false;
    },
  });
  const latest = followed.data ?? posted.data;
  const waiting =
    enabled &&
    !posted.isError &&
    !followed.isError &&
    (posted.isPending ||
      latest === undefined ||
      latest.status === "pending" ||
      latest.status === "idle");
  return {
    face: readingFace(latest, waiting, posted.isError || followed.isError),
    data: latest,
  };
}
