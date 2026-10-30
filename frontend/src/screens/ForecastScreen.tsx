import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  ApiRequestError,
  getFavorites,
  getShare,
  readingKey,
  saveFavorite,
  spendStars,
} from "../api/client";
import { forecastTopics, getForecastTopics } from "../api/fixtures";
import { queryKeys } from "../api/keys";
import { STAR_SILENCE, useReading } from "../readingWait";
import { Button } from "../shared/ui/Button/Button";
import { ListRow } from "../shared/ui/ListRow/ListRow";
import { Screen } from "../shared/ui/Screen/Screen";
import { Skeleton } from "../shared/ui/Skeleton/Skeleton";
import { StarPrice } from "../shared/ui/StarPrice/StarPrice";
import { SegmentedControl } from "../shared/ui/SegmentedControl/SegmentedControl";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import { holdStarBalance, writeStarBalance } from "../starBalance";
import { WEEK_STARS } from "../stars";
import { formatRuDate } from "./format";
import styles from "./screens.module.css";
import { TopUpDialog } from "./TopUpDialog";
import { useTopicDetail } from "./topicDetail";

const PERIODS = [
  { id: "day", label: "День" },
  { id: "week", label: "Неделя" },
  { id: "month", label: "Месяц" },
] as const;

type Period = (typeof PERIODS)[number]["id"];

const KIND: Record<Period, string> = {
  day: "day",
  week: "week",
  month: "personal_month",
};

function shortenTopicText(text: string, maxWords: number = 4): string {
  const words = text.trim().replace(/\.$/, "").split(/\s+/);
  if (words.length <= maxWords) {
    return text.trim();
  }
  return words.slice(0, maxWords).join(" ");
}

export function ForecastScreen({ premium }: { premium: boolean }) {
  const [period, setPeriod] = useState<Period>("day");
  const [topUp, setTopUp] = useState(false);
  const client = useQueryClient();
  const topics = useQuery({ queryKey: queryKeys.forecastTopics, queryFn: getForecastTopics });
  const favorites = useQuery({ queryKey: queryKeys.favorites, queryFn: () => getFavorites() });
  const reading = useReading(KIND[period]);
  const isUnlocked = premium || (period !== "day" && reading.face.phase === "ready");
  const detail = useTopicDetail(isUnlocked);
  const historyId = reading.face.phase === "ready" ? reading.face.historyId : null;

  const buy = useMutation({
    mutationFn: () =>
      spendStars({
        feature: period === "week" ? "week" : "month",
      }),
    onMutate: () => holdStarBalance(client, WEEK_STARS),
    onSuccess: async (ticket, _variables, restore) => {
      if (ticket.charged) {
        writeStarBalance(client, ticket.balance);
      } else {
        restore?.();
      }
      await client.invalidateQueries({ queryKey: queryKeys.reading(KIND[period]) });
    },
    onError: (error, _variables, restore) => {
      restore?.();
      if (error instanceof ApiRequestError && error.status === 402) {
        setTopUp(true);
      }
    },
  });

  const keep = useMutation({
    mutationFn: (id: string) => saveFavorite(id, readingKey()),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: queryKeys.favorites });
    },
  });
  const saved =
    historyId !== null &&
    (favorites.data?.some((item) => item.history_id === historyId) === true ||
      (keep.isSuccess && keep.variables === historyId));
  const share = useMutation({
    mutationFn: async () => {
      const historyId = reading.face.phase === "ready" ? reading.face.historyId : null;
      const link = historyId ? await getShare(historyId) : window.location.href;
      if (navigator.share) {
        await navigator.share({ title: "Ваш прогноз", url: link });
        return;
      }
      await navigator.clipboard.writeText(link);
    },
  });

  const rows = topics.data ?? forecastTopics;
  const topicPreviews = reading.data?.topics ?? {};

  return (
    <Screen tab="today">
      <TopBar title="Ваш прогноз" align="left" />
      <SegmentedControl
        label="Период прогноза"
        value={period}
        options={PERIODS}
        onChange={setPeriod}
      />
      <p className={styles.kicker}>{formatRuDate(new Date())}</p>
      {period !== "day" && reading.face.phase === "stars" ? (
        <section className={styles.reading}>
          <h2>Прогноз на {period === "week" ? "неделю" : "месяц"}</h2>
          <p>
            Прогноз на {period === "week" ? "неделю" : "месяц"} стоит{" "}
            <StarPrice amount={WEEK_STARS} /> звёзд. С Premium он входит в период.
          </p>
          <Button loading={buy.isPending} onClick={() => buy.mutate()}>
            Открыть за <StarPrice amount={WEEK_STARS} />
          </Button>
        </section>
      ) : reading.face.phase === "loading" ? (
        <Skeleton lines={4} />
      ) : (
        <p className={styles.paragraph}>
          {reading.face.phase === "ready" ? reading.face.body : STAR_SILENCE}
        </p>
      )}
      <div className={styles.stack}>
        {rows.map((row) => {
          const preview = shortenTopicText(topicPreviews[row.id] || row.subtitle);
          return (
            <ListRow
              key={row.id}
              icon={row.icon}
              title={row.title}
              subtitle={preview}
              chevron
              onClick={() => {
                if (period !== "day" && reading.face.phase === "stars") {
                  buy.mutate();
                } else {
                  detail.open(row.id, row.title);
                }
              }}
            />
          );
        })}
      </div>
      <div className={styles.actions}>
        <Button
          variant="secondary"
          icon="save_bookmark"
          fit
          disabled={historyId === null || saved || keep.isPending || favorites.isPending}
          onClick={() => {
            if (historyId === null) {
              return;
            }
            keep.mutate(historyId);
          }}
        >
          {saved ? "Сохранено" : "Сохранить"}
        </Button>
        <Button
          icon="share"
          fit
          onClick={() => {
            share.mutate();
          }}
        >
          Поделиться
        </Button>
      </div>
      {detail.dialog}
      {topUp ? <TopUpDialog balance={null} onClose={() => setTopUp(false)} /> : null}
    </Screen>
  );
}
