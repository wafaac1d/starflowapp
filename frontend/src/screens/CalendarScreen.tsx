import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router";

import { getLunarCopy, lunarSample } from "../api/fixtures";
import { queryKeys } from "../api/keys";
import { Icon } from "../shared/ui/Icon/Icon";
import { LunarCalendar } from "../shared/ui/LunarCalendar/LunarCalendar";
import { longDate, phaseFor } from "../shared/ui/LunarCalendar/phase";
import { Screen } from "../shared/ui/Screen/Screen";
import { Skeleton } from "../shared/ui/Skeleton/Skeleton";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

export function CalendarScreen() {
  const [params] = useSearchParams();
  const seeded = params.get("day") ?? "";
  const today = new Date();
  const initial = seeded === "" ? isoFromDate(today) : seeded;
  const initialDate = parseIso(initial);
  const [cursor, setCursor] = useState({ year: initialDate.year, month: initialDate.month });
  const [selected, setSelected] = useState(initial);
  const copy = useQuery({
    queryKey: queryKeys.lunarDay(selected),
    queryFn: () => getLunarCopy(selected),
  });
  const phase = phaseFor(selected);
  const note = copy.data?.note ?? "";
  const phaseLabel = selected === lunarSample.iso ? lunarSample.phase : (copy.data?.phase ?? phase.label);
  const shift = (delta: number) => {
    const next = new Date(cursor.year, cursor.month - 1 + delta, 1);
    setCursor({ year: next.getFullYear(), month: next.getMonth() + 1 });
  };
  return (
    <Screen tab="calendar">
      <TopBar title="Лунный календарь" back />
      <LunarCalendar
        year={cursor.year}
        month={cursor.month}
        selected={selected}
        onSelect={setSelected}
        onPrevious={() => {
          shift(-1);
        }}
        onNext={() => {
          shift(1);
        }}
      />
      <article className={styles.dayCard}>
        <Icon name="crescent_peach" size={28} />
        <div className={styles.dayCopy}>
          <h3>{longDate(selected)}</h3>
          <p>{phaseLabel}</p>
          {copy.isPending ? <Skeleton lines={2} /> : null}
          {note !== "" ? <p>{note}</p> : null}
        </div>
      </article>
    </Screen>
  );
}

function isoFromDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function parseIso(iso: string): { year: number; month: number } {
  const parts = iso.split("-");
  const year = Number(parts[0]);
  const month = Number(parts[1]);
  if (!Number.isFinite(year) || !Number.isFinite(month)) {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  }
  return { year, month };
}
