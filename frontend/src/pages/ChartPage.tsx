import { useQuery } from "@tanstack/react-query";

import { getChart, getSky, type ChartResponse } from "../api/client";
import { BackHome, Button, LoadingScreen } from "../components/ui/controls";
import { text, type TextKey } from "../resources";

const LIMITATIONS: Record<string, TextKey> = {
  time_unknown: "ui.chart.time_unknown",
  place_missing: "ui.chart.place_missing",
  local_time_ambiguous: "ui.chart.local_time_ambiguous",
  local_time_gap: "ui.chart.local_time_gap",
  timezone_missing: "ui.chart.timezone_missing",
  birth_date_missing: "ui.chart.birth_date_missing",
  houses_unavailable: "ui.chart.houses_unavailable",
};

type ChartPageProps = {
  fetchImpl?: typeof fetch;
};

export function ChartPage({ fetchImpl = fetch }: ChartPageProps) {
  const chart = useQuery({
    queryKey: ["chart"],
    queryFn: () => getChart(fetchImpl),
    retry: false,
  });
  const sky = useQuery({
    queryKey: ["sky"],
    queryFn: () => getSky(fetchImpl),
    retry: false,
  });
  if (chart.isPending) {
    return <LoadingScreen />;
  }
  return (
    <main className="shell">
      <section className="surface">
        <h1>{text("ui.chart.title")}</h1>
        {chart.isError ? (
          <>
            <p role="alert">{text("ui.common.error")}</p>
            <Button
              label={text("ui.common.retry")}
              onClick={() => {
                void chart.refetch();
              }}
            />
          </>
        ) : null}
        {chart.data !== undefined ? <ChartDetails chart={chart.data} /> : null}
        {sky.data !== undefined ? (
          <>
            <h2>{text("ui.sky.title")}</h2>
            <p className="lead">{text("ui.sky.lead")}</p>
            <p>
              {text("ui.chart.phase")}: {sky.data.phase_name}
            </p>
          </>
        ) : null}
        <p className="disclaimer">{text("ui.home.disclaimer")}</p>
        <div className="actions">
          <BackHome />
        </div>
      </section>
    </main>
  );
}

function ChartDetails({ chart }: { chart: ChartResponse }) {
  const source =
    chart.sun_sign_source === "ephemeris"
      ? text("ui.chart.ephemeris_source")
      : text("ui.chart.calendar_source");
  return (
    <>
      <h2>{text("ui.chart.sun")}</h2>
      <p className="lead">{chart.sun_sign ?? text("ui.chart.birth_date_missing")}</p>
      <p className="meta">{source}</p>
      <p>{chart.moon_sign === null ? text("ui.chart.moon_unknown") : chart.moon_sign}</p>
      <p>
        {chart.ascendant_sign === null ? text("ui.chart.asc_unknown") : chart.ascendant_sign}
      </p>
      <p>
        {chart.houses === null ? text("ui.chart.houses_unknown") : chart.houses.join(", ")}
      </p>
      {chart.limitations.map((code) => (
        <p key={code}>{limitationText(code)}</p>
      ))}
      {chart.lunar_day !== null ? (
        <p>
          {text("ui.chart.lunar_day")}: {chart.lunar_day}
        </p>
      ) : null}
      {chart.phase_name !== null ? (
        <p>
          {text("ui.chart.phase")}: {chart.phase_name}
        </p>
      ) : null}
      {chart.planets.length > 0 ? (
        <>
          <h2>{text("ui.chart.planets")}</h2>
          <ul>
            {chart.planets.map((planet) => (
              <li key={planet.name}>
                {planet.name}
                {planet.sign === null ? "" : `, ${planet.sign}`}
                {planet.retrograde ? `, ${text("ui.chart.retrograde")}` : ""}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {chart.transits.length > 0 ? (
        <>
          <h2>{text("ui.chart.transits")}</h2>
          <ul>
            {chart.transits.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}
      {chart.natal_access === "premium_required" ? (
        <>
          <h2>{text("ui.paywall.title")}</h2>
          <p className="lead">{text("ui.paywall.lead")}</p>
        </>
      ) : null}
    </>
  );
}

function limitationText(code: string): string {
  const key = LIMITATIONS[code];
  if (key === undefined) {
    return code;
  }
  return text(key);
}
