import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { describeIso, isoInZone, monthDays, shiftMonth } from "../almanacDate";
import { getReading, readingKey, startReading, type CalendarDay } from "../api/client";
import { Divider, EditorialListRow, TimelineItem, WeekDaySelector } from "../components/ui/editorial";
import { Button, IconButton } from "../components/ui/controls";
import { deviceTimezone } from "../deviceZone";
import { formatText, text } from "../resources";
import { ScoreLegend, scoreWord } from "./ReadingPage";

export function CalendarPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const zone = deviceTimezone();
  const today = isoInZone(new Date(), zone);
  const selected = params.get("day") ?? today;
  const current = describeIso(selected, zone);
  const days = monthDays(selected, zone);
  const dateLabel = `${current.day} ${current.month}`;

  function choose(iso: string) {
    const next = new URLSearchParams(params);
    next.set("day", iso);
    setParams(next, { replace: true });
  }

  return (
    <main className="shell">
      <div className="week-head">
        <div>
          <h1>{current.month}</h1>
          <p className="lead">{text("ui.calendar.rhythm")}</p>
        </div>
      </div>
      <WeekDaySelector days={days} selected={selected} onSelect={choose} />
      <Divider />
      <p className="day-heading">
        {current.day} / {current.weekday}
      </p>
      <div className="timeline">
        <TimelineItem
          marker="circle"
          title={text("ui.calendar.relations")}
          body={formatText("ui.calendar.relations_body", { date: dateLabel })}
          onClick={() => {
            void navigate("/reading/compatibility");
          }}
        />
        <TimelineItem
          marker="square"
          title={text("ui.calendar.work")}
          body={formatText("ui.calendar.work_body", { date: dateLabel })}
          onClick={() => {
            void navigate("/reading/week");
          }}
        />
        <TimelineItem
          marker="triangle"
          title={text("ui.calendar.self")}
          body={formatText("ui.calendar.self_body", { date: dateLabel })}
          onClick={() => {
            void navigate("/reading/advice");
          }}
        />
      </div>
      <div className="editorial-list">
        <EditorialListRow
          label={text("ui.reading.today_detail")}
          arrow
          onClick={() => {
            void navigate("/reading/today_detail");
          }}
        />
        <EditorialListRow
          label={text("ui.reading.tomorrow")}
          arrow
          onClick={() => {
            void navigate("/reading/tomorrow");
          }}
        />
      </div>
      <div className="actions">
        <Button
          tone="outline"
          label={text("ui.calendar.all_month")}
          onClick={() => {
            void navigate(`/calendar/month?month=${selected.slice(0, 7)}-01`);
          }}
        />
      </div>
    </main>
  );
}

export function MonthPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const zone = deviceTimezone();
  const today = isoInZone(new Date(), zone);
  const anchor = params.get("month") ?? today;
  const current = describeIso(anchor, zone);
  const days = monthDays(anchor, zone);
  const month = anchor.slice(0, 7);
  const marks = useMonthMarks(month);

  function move(delta: number) {
    const next = new URLSearchParams(params);
    next.set("month", shiftMonth(anchor, delta));
    setParams(next, { replace: true });
  }

  return (
    <main className="shell">
      <div className="week-head">
        <h1>{current.month}</h1>
        <div className="thumb-row">
          <IconButton
            label={text("ui.calendar.prev")}
            name="arrow-left"
            onClick={() => {
              move(-1);
            }}
          />
          <IconButton
            label={text("ui.calendar.next")}
            name="arrow-right"
            onClick={() => {
              move(1);
            }}
          />
        </div>
      </div>
      <ScoreLegend />
      {marks.status === "premium" ? <p>{text("ui.paywall.lead")}</p> : null}
      <div className="month-grid">
        {days.map((item) => {
          const mark = marks.byDay.get(item.iso);
          const label = mark === undefined ? String(item.day) : `${item.day}, ${scoreWord(mark)}`;
          return (
            <button
              key={item.iso}
              type="button"
              className={item.iso === today ? "week-day week-day-active" : "week-day"}
              aria-label={label}
              onClick={() => {
                void navigate(`/calendar?day=${item.iso}`);
              }}
            >
              <strong>{item.day}</strong>
              {mark === undefined ? null : <span>{scoreWord(mark)}</span>}
            </button>
          );
        })}
      </div>
    </main>
  );
}

function useMonthMarks(month: string): { status: string; byDay: Map<string, number> } {
  const [attempt] = useState(0);
  const start = useMutation({
    mutationFn: () => startReading("calendar", readingKey(), fetch, { month }),
  });
  useEffect(() => {
    start.mutate();
    // The month key is the request identity; the mutation object is not.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month, attempt]);
  const reading = useQuery({
    queryKey: ["calendar-month", month],
    queryFn: () => getReading("calendar", fetch, { month }),
    enabled: start.isSuccess,
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 700 : false),
  });
  const byDay = new Map<string, number>();
  const days: CalendarDay[] = reading.data?.days ?? start.data?.days ?? [];
  for (const day of days) {
    const values = Object.values(day.scores);
    if (values.length > 0) {
      byDay.set(day.date, Math.round(values.reduce((sum, item) => sum + item, 0) / values.length));
    }
  }
  return { status: reading.data?.status ?? start.data?.status ?? "idle", byDay };
}
