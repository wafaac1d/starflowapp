import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getReading, getShare, readingKey, saveFavorite, startReading } from "../api/client";
import { forecastBody, forecastTopics, getForecastTopics } from "../api/fixtures";
import { queryKeys } from "../api/keys";
import { Button } from "../shared/ui/Button/Button";
import { ListRow } from "../shared/ui/ListRow/ListRow";
import { Screen } from "../shared/ui/Screen/Screen";
import { SegmentedControl } from "../shared/ui/SegmentedControl/SegmentedControl";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import { formatRuDate } from "./format";
import styles from "./screens.module.css";

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

export function ForecastScreen() {
  const [period, setPeriod] = useState<Period>("day");
  const topics = useQuery({ queryKey: queryKeys.forecastTopics, queryFn: getForecastTopics });
  const reading = useQuery({
    queryKey: queryKeys.reading(KIND[period]),
    queryFn: async () => {
      const started = await startReading(KIND[period], readingKey());
      if (started.status === "ready" || started.status === "fallback") {
        return started;
      }
      return getReading(KIND[period]);
    },
  });
  const keep = useMutation({
    mutationFn: () => saveFavorite(reading.data?.history_id ?? "", readingKey()),
  });
  const share = useMutation({
    mutationFn: async () => {
      const historyId = reading.data?.history_id;
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
        label="период прогноза"
        value={period}
        options={PERIODS}
        onChange={setPeriod}
      />
      <p className={styles.kicker}>{formatRuDate(new Date())}</p>
      <p className={styles.paragraph}>{reading.data?.body || forecastBody}</p>
      <div className={styles.stack}>
        {rows.map((row) => (
          <ListRow key={row.id} icon={row.icon} title={row.title} subtitle={row.subtitle} chevron />
        ))}
      </div>
      <div className={styles.actions}>
        <Button
          variant="secondary"
          icon="save_bookmark"
          fit
          disabled={reading.data?.history_id == null || keep.isSuccess}
          onClick={() => {
            keep.mutate();
          }}
        >
          Сохранить
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
    </Screen>
  );
}
