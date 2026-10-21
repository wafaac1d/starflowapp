import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  getReading,
  getShare,
  readingKey,
  saveFavorite,
  sendFeedback,
  startReading,
  type ReadingResponse,
} from "../api/client";
import { BackHome, Button } from "../components/ui/controls";
import { text, type TextKey } from "../resources";

const TITLES: Record<string, TextKey> = {
  day: "ui.reading.day",
  week: "ui.reading.week",
  advice: "ui.reading.advice",
  moon: "ui.reading.moon",
  compatibility: "ui.reading.compatibility",
};

type ReadingPageProps = {
  kind: string;
  fetchImpl?: typeof fetch;
  pollMs?: number;
};

export function ReadingPage({ kind, fetchImpl = fetch, pollMs = 700 }: ReadingPageProps) {
  const [attempt, setAttempt] = useState(0);
  const [postedAttempt, setPostedAttempt] = useState<number | null>(null);
  const [shareText, setShareText] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const title = text(TITLES[kind] ?? "ui.reading.day");
  const start = useMutation({
    mutationFn: (_next: number) => startReading(kind, readingKey(), fetchImpl),
    onSuccess: (_data, next) => {
      setPostedAttempt(next);
    },
  });
  useEffect(() => {
    start.mutate(attempt);
    // Listing the mutation object here would post again on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt, kind]);
  const reading = useQuery({
    queryKey: ["reading", kind, attempt],
    queryFn: () => getReading(kind, fetchImpl),
    enabled: postedAttempt === attempt,
    refetchInterval: (query) => (query.state.data?.status === "pending" ? pollMs : false),
  });
  const polled = reading.data !== undefined && reading.data.status !== "idle" ? reading.data : undefined;
  const data = postedAttempt === attempt ? polled ?? start.data : undefined;
  const failed = data?.status === "error" || start.isError;
  const waiting = !failed && (data === undefined || data.status === "pending" || start.isPending);

  return (
    <main className="shell">
      <h1>{title}</h1>
      {waiting ? <p>{text("ui.reading.pending")}</p> : null}
      {failed ? (
        <>
          <p role="alert">{data?.body || text("ui.common.error")}</p>
          <Button
            label={text("ui.common.retry")}
            onClick={() => {
              setShareText(null);
              setAttempt((value) => value + 1);
            }}
          />
        </>
      ) : null}
      {data !== undefined && (data.status === "ready" || data.status === "fallback") ? (
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
      <BackHome />
    </main>
  );
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
      {data.status === "fallback" ? <p>{text("ui.reading.fallback")}</p> : null}
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
      {data.title !== null ? <h2>{data.title}</h2> : null}
      {data.body !== null ? <p>{data.body}</p> : null}
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
            label={saved ? text("ui.reading.save") : text("ui.reading.save")}
            onClick={() => {
              keep.mutate();
            }}
            disabled={saved}
          />
          <Button
            label={text("ui.reading.share")}
            onClick={() => {
              share.mutate();
            }}
          />
          {shareText !== null ? <p className="reading-copy">{shareText}</p> : null}
        </>
      ) : null}
    </>
  );
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
