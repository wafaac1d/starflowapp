import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { describeIso, isoInZone } from "../almanacDate";
import { getReading } from "../api/client";
import type { ProfileResponse } from "../api/client";
import { Skeleton } from "../components/ui/controls";
import { DateHero, EditorialListRow, WineStatement } from "../components/ui/editorial";
import { deviceTimezone } from "../deviceZone";
import { text, type TextKey } from "../resources";

type HomePageProps = {
  profile: ProfileResponse;
};

const ROWS: { to: string; label: TextKey; index: string }[] = [
  { to: "/reading/day", label: "ui.home.row_day", index: "01" },
  { to: "/reading/moon", label: "ui.home.row_moon", index: "02" },
  { to: "/reading/advice", label: "ui.home.row_advice", index: "03" },
];

export function HomePage({ profile: _profile }: HomePageProps) {
  const navigate = useNavigate();
  const zone = deviceTimezone();
  const today = describeIso(isoInZone(new Date(), zone), zone);
  const reading = useQuery({
    queryKey: ["reading", "day"],
    queryFn: () => getReading("day"),
  });
  const ready = reading.data?.status === "ready" || reading.data?.status === "fallback";
  const title = ready ? reading.data?.title : null;

  return (
    <main className="shell">
      <DateHero
        month={today.month}
        weekday={today.weekday}
        day={today.day}
        lineOne={text("ui.home.day_line_1")}
        lineTwo={text("ui.home.day_line_2")}
      />
      <WineStatement kicker={text("ui.home.kicker")}>
        {reading.isPending ? <Skeleton /> : null}
        {reading.isPending ? null : title !== null && title !== "" ? (
          title
        ) : (
          <>
            {text("ui.home.statement_1")}
            <br />
            {text("ui.home.statement_2")}
          </>
        )}
      </WineStatement>
      <div className="editorial-list">
        {ROWS.map((row) => (
          <EditorialListRow
            key={row.to}
            index={row.index}
            label={text(row.label)}
            arrow
            onClick={() => {
              void navigate(row.to);
            }}
          />
        ))}
      </div>
      <p className="home-note">{text("ui.home.disclaimer")}</p>
    </main>
  );
}
