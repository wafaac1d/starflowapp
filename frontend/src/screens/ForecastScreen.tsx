import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { getFavorites, getShare, readingKey, saveFavorite } from "../api/client";
import { forecastTopics, getForecastTopics } from "../api/fixtures";
import { queryKeys } from "../api/keys";
import { STAR_SILENCE, useReading } from "../readingWait";
import { Button } from "../shared/ui/Button/Button";
import { ListRow } from "../shared/ui/ListRow/ListRow";
import { Screen } from "../shared/ui/Screen/Screen";
import { Skeleton } from "../shared/ui/Skeleton/Skeleton";
import { SegmentedControl } from "../shared/ui/SegmentedControl/SegmentedControl";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import { formatRuDate } from "./format";
import styles from "./screens.module.css";
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

export function ForecastScreen({ premium }: { premium: boolean }) {
  const [period, setPeriod] = useState<Period>("day");
  const client = useQueryClient();
  const detail = useTopicDetail(premium);
  const topics = useQuery({ queryKey: queryKeys.forecastTopics, queryFn: getForecastTopics });
  const favorites = useQuery({ queryKey: queryKeys.favorites, queryFn: () => getFavorites() });
  const reading = useReading(KIND[period]);
  const historyId = reading.face.phase === "ready" ? reading.face.historyId : null;
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
      {reading.face.phase === "loading" ? (
        <Skeleton lines={4} />
      ) : (
        <p className={styles.paragraph}>
          {reading.face.phase === "ready" ? reading.face.body : STAR_SILENCE}
        </p>
      )}
      <div className={styles.stack}>
        {rows.map((row) => (
          <ListRow
            key={row.id}
            icon={row.icon}
            title={row.title}
            subtitle={row.subtitle}
            chevron
            onClick={() => {
              detail.open(row.id, row.title);
            }}
          />
        ))}
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
    </Screen>
  );
}
