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

export type ReadingFace =
  | { phase: "loading" }
  | { phase: "ready"; title: string; body: string; historyId: string | null }
  | { phase: "premium" }
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
  if (data.status === "blocked" || data.status === "limit") {
    return { phase: "blocked", body: data.body ?? STAR_SILENCE };
  }
  if (data.status === "ready" && data.body != null && data.body !== "") {
    const title = data.title != null && data.title !== "" ? data.title : data.body;
    return { phase: "ready", title, body: data.body, historyId: data.history_id };
  }
  return { phase: "miss" };
}

export function useReading(kind: string, query: ReadingQuery = {}, enabled = true) {
  const keys = useRef<Record<string, string>>({});
  const scope = `${kind}|${query.topic ?? ""}|${query.month ?? ""}|${query.relatedId ?? ""}`;
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
