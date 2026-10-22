import { useNavigate, useSearchParams } from "react-router";

import { describeIso, isoInZone, monthDays, shiftMonth } from "../almanacDate";
import { Divider, TimelineItem, WeekDaySelector } from "../components/ui/editorial";
import { Button, IconButton } from "../components/ui/controls";
import { deviceTimezone } from "../deviceZone";
import { formatText, text } from "../resources";

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
      <div className="month-grid">
        {days.map((item) => (
          <button
            key={item.iso}
            type="button"
            className={item.iso === today ? "week-day week-day-active" : "week-day"}
            onClick={() => {
              void navigate(`/calendar?day=${item.iso}`);
            }}
          >
            <strong>{item.day}</strong>
          </button>
        ))}
      </div>
    </main>
  );
}
