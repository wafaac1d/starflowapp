import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import {
  getReading,
  getShare,
  readingKey,
  saveFavorite,
  sendFeedback,
  startReading,
  type CalendarDay,
  type ReadingQuery,
  type ReadingResponse,
} from "../api/client";
import { describeIso, isoInZone } from "../almanacDate";
import { Button, Skeleton } from "../components/ui/controls";
import { PageHeader, PeriodTabs } from "../components/ui/editorial";
import { deviceTimezone } from "../deviceZone";
import { STAR_SILENCE } from "../readingWait";
import { text, type TextKey } from "../resources";

const TITLES: Record<string, TextKey> = {
  day: "ui.reading.day",
  week: "ui.reading.week",
  advice: "ui.reading.advice",
  moon: "ui.reading.moon",
  compatibility: "ui.reading.compatibility",
  today_detail: "ui.reading.today_detail",
  tomorrow: "ui.reading.tomorrow",
  personal_day: "ui.reading.personal_day",
  personal_week: "ui.reading.personal_week",
  personal_month: "ui.reading.personal_month",
  topics: "ui.reading.topics",
  calendar: "ui.reading.calendar",
  synastry: "ui.reading.synastry",
};

type ReadingPageProps = {
  kind: string;
  fetchImpl?: typeof fetch;
  pollMs?: number;
};

const PERIOD_KIND: Record<string, { day: string; week: string; month: string }> = {
  day: { day: "day", week: "week", month: "personal_month" },
  week: { day: "day", week: "week", month: "personal_month" },
  personal_day: { day: "personal_day", week: "personal_week", month: "personal_month" },
  personal_week: { day: "personal_day", week: "personal_week", month: "personal_month" },
  personal_month: { day: "personal_day", week: "personal_week", month: "personal_month" },
};

type StartVars = {
  key: string;
  kind: string;
  query: ReadingQuery;
};

export function ReadingPage({ kind, fetchImpl = fetch, pollMs = 700 }: ReadingPageProps) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const topic = params.get("topic");
  const month = params.get("month");
  const relatedId = params.get("related_id");
  const query: ReadingQuery = {};
  if (topic) {
    query.topic = topic;
  }
  if (month) {
    query.month = month;
  }
  if (relatedId) {
    query.relatedId = relatedId;
  }
  const [attempt, setAttempt] = useState(0);
  const [posted, setPosted] = useState<ReadingResponse | null>(null);
  const [postedKey, setPostedKey] = useState<string | null>(null);
  const [shareText, setShareText] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const requestKey = `${kind}|${topic ?? ""}|${month ?? ""}|${relatedId ?? ""}|${attempt}`;
  const latest = useRef(requestKey);
  latest.current = requestKey;
  const title = text(TITLES[kind] ?? "ui.reading.day");
  const start = useMutation({
    mutationFn: (vars: StartVars) => startReading(vars.kind, readingKey(), fetchImpl, vars.query),
    onSuccess: (next, vars) => {
      if (vars.key !== latest.current) {
        return;
      }
      setPosted(next);
      setPostedKey(vars.key);
    },
  });
  useEffect(() => {
    setSaved(false);
    setShareText(null);
    start.mutate({ key: requestKey, kind, query });
    // Listing the mutation object here would post again on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey]);
  const current = postedKey === requestKey;
  const reading = useQuery({
    queryKey: ["reading", requestKey],
    queryFn: () => getReading(kind, fetchImpl, query),
    enabled: current,
    refetchInterval: (query) => (query.state.data?.status === "pending" ? pollMs : false),
  });
  const polled = reading.data !== undefined && reading.data.status !== "idle" ? reading.data : undefined;
  const data: ReadingResponse | undefined = current ? (polled ?? posted ?? undefined) : undefined;
  const failed = data?.status === "error" || start.isError;
  const waiting = !failed && (data === undefined || data.status === "pending" || start.isPending);

  const period = PERIOD_KIND[kind];
  const today = describeIso(isoInZone(new Date(), deviceTimezone()), deviceTimezone());
  const active = periodValue(kind);
  return (
    <main className="shell page">
      {period !== undefined ? (
        <p className="reading-kicker">
          {today.day} {today.month} / {today.weekday}
        </p>
      ) : null}
      <PageHeader title={data?.title || title} backTo="/" />
      {period !== undefined && active !== null ? (
        <PeriodTabs
          value={active}
          onChange={(next) => {
            void navigate(`/reading/${period[next]}`);
          }}
        />
      ) : null}
      {waiting ? (
        <div role="status" aria-label="Ждём ответ">
          <Skeleton />
        </div>
      ) : null}
      {failed || data?.status === "fallback" ? (
        <>
          <p role="alert">{STAR_SILENCE}</p>
          <Button
            label={text("ui.common.retry")}
            onClick={() => {
              setShareText(null);
              setAttempt((value) => value + 1);
            }}
          />
        </>
      ) : null}
      {data !== undefined && data.status === "ready" ? (
        <ReadingBody
          data={data}
          saved={saved}
          shareText={shareText}
          fetchImpl={fetchImpl}
          onSaved={() => {
            setSaved(true);
          }}
          onShare={setShareText}
        />
      ) : null}
      {data?.status === "blocked" || data?.status === "limit" || data?.status === "premium" ? (
        <p role="alert">{data.body || text("ui.common.error")}</p>
      ) : null}
      {data?.status === "premium" ? (
        <Button
          label={text("ui.premium.title")}
          onClick={() => {
            void navigate("/premium");
          }}
        />
      ) : null}
      {data?.days !== undefined && data.days.length > 0 ? <DayScores days={data.days} /> : null}
    </main>
  );
}

function periodValue(kind: string): "day" | "week" | "month" | null {
  if (kind === "week" || kind === "personal_week") {
    return "week";
  }
  if (kind === "personal_month") {
    return "month";
  }
  if (kind === "day" || kind === "personal_day") {
    return "day";
  }
  return null;
}

type BodyProps = {
  data: ReadingResponse;
  saved: boolean;
  shareText: string | null;
  fetchImpl: typeof fetch;
  onSaved: () => void;
  onShare: (value: string) => void;
};

function ReadingBody({ data, saved, shareText, fetchImpl, onSaved, onShare }: BodyProps) {
  const feedback = useMutation({
    mutationFn: (score: number) => sendFeedback(data.history_id || "", score, fetchImpl),
  });
  const keep = useMutation({
    mutationFn: () => saveFavorite(data.history_id || "", readingKey(), fetchImpl),
    onSuccess: onSaved,
  });
  const share = useMutation({
    mutationFn: () => getShare(data.history_id || "", fetchImpl),
    onSuccess: onShare,
  });
  return (
    <>
      {data.greeting !== null ? <p>{data.greeting}</p> : null}
      {data.user_sign !== null ? (
        <p>
          {text("ui.reading.sign_label")}: {data.user_sign}
        </p>
      ) : null}
      {data.streak !== null ? (
        <p>
          {data.streak} {text("ui.reading.streak")}
        </p>
      ) : null}
      {data.body !== null
        ? data.body.split(/\n{2,}/).map((part, index) => (
            <p key={`${index}-${part.slice(0, 24)}`} className="reading-body">
              {part}
            </p>
          ))
        : null}
      {data.shared_facts !== null ? (
        <p>
          {text("ui.reading.facts_label")}: {data.shared_facts}
        </p>
      ) : null}
      {data.history_id !== null ? (
        <>
          <div className="thumb-row">
            <button
              type="button"
              className="button"
              aria-label={text("ui.reading.useful")}
              onClick={() => {
                feedback.mutate(5);
              }}
            >
              <Thumb direction="up" />
            </button>
            <button
              type="button"
              className="button"
              aria-label={text("ui.reading.not_useful")}
              onClick={() => {
                feedback.mutate(1);
              }}
            >
              <Thumb direction="down" />
            </button>
          </div>
          <Button
            tone="outline"
            icon="bookmark"
            label={text("ui.reading.save")}
            onClick={() => {
              keep.mutate();
            }}
            disabled={saved}
          />
          <Button
            tone="outline"
            icon="share"
            label={text("ui.reading.share")}
            onClick={() => {
              share.mutate();
            }}
          />
          {shareText !== null ? <p className="reading-copy">{shareText}</p> : null}
        </>
      ) : null}
      <p className="home-note">{text("ui.home.disclaimer")}</p>
    </>
  );
}

function DayScores({ days }: { days: CalendarDay[] }) {
  return (
    <>
      <ScoreLegend />
      {days.map((day) => (
        <article key={day.date}>
          <h2>{day.date}</h2>
          {Object.entries(day.scores).map(([theme, score]) => (
            <p key={theme} className="score-row">
              <span>{theme}</span>
              <span>
                {score} · {scoreWord(score)}
              </span>
            </p>
          ))}
          <p>{day.note}</p>
        </article>
      ))}
    </>
  );
}

export function ScoreLegend() {
  return (
    <ul className="legend" aria-label={text("ui.calendar.legend")}>
      <li>
        <span className="legend-mark" aria-hidden="true" />
        {text("ui.calendar.low")} 1–2
      </li>
      <li>
        <span className="legend-mark" aria-hidden="true" />
        {text("ui.calendar.mid")} 3
      </li>
      <li>
        <span className="legend-mark" aria-hidden="true" />
        {text("ui.calendar.high")} 4–5
      </li>
    </ul>
  );
}

export function scoreWord(score: number): string {
  if (score <= 2) {
    return text("ui.calendar.low");
  }
  if (score === 3) {
    return text("ui.calendar.mid");
  }
  return text("ui.calendar.high");
}

function Thumb({ direction }: { direction: "up" | "down" }) {
  const path =
    direction === "up"
      ? "M8 11v8.5M8 11l3.1-6.1a1.7 1.7 0 0 1 1.5-1h.1a1.6 1.6 0 0 1 1.6 1.8L14 11h3.1a2 2 0 0 1 2 2.2l-.7 5.1a2 2 0 0 1-2 1.7H8"
      : "M8 13V4.5M8 13l3.1 6.1a1.7 1.7 0 0 0 1.5 1h.1a1.6 1.6 0 0 0 1.6-1.8L14 13h3.1a2 2 0 0 0 2-2.2l-.7-5.1a2 2 0 0 0-2-1.7H8";
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d={path}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
