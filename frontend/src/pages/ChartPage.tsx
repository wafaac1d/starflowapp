import { useQuery, useQueryClient } from "@tanstack/react-query";

import { getChart, getSky, type ChartResponse, type ProfileResponse } from "../api/client";
import { ErrorState, LoadingScreen } from "../components/ui/controls";
import { NatalChartView, PageHeader } from "../components/ui/editorial";
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
  const client = useQueryClient();
  const profile = client.getQueryData<ProfileResponse>(["session"]);
  if (chart.isPending) {
    return <LoadingScreen />;
  }
  return (
    <main className="shell page">
      <section>
        <PageHeader title={text("ui.chart.title")} backTo="/profile" />
        {profile !== undefined ? <BirthFacts profile={profile} /> : null}
        {chart.isError ? (
          <ErrorState
            message={text("ui.common.error")}
            onRetry={() => {
              void chart.refetch();
            }}
          />
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
      </section>
    </main>
  );
}

function BirthFacts({ profile }: { profile: ProfileResponse }) {
  const unknown =
    profile.birth_time_unknown || profile.birth_time === null || profile.birth_time.trim() === "";
  const time = unknown ? text("ui.profile.time_missing") : profile.birth_time;
  const place = profile.birth_place;
  return (
    <p className="profile-meta">
      {profile.birth_date ?? text("ui.profile.date_missing")}
      {" · "}
      {time}
      {place !== null && place !== "" ? ` · ${place}` : ""}
    </p>
  );
}

function ChartDetails({ chart }: { chart: ChartResponse }) {
  const source =
    chart.sun_sign_source === "ephemeris"
      ? text("ui.chart.ephemeris_source")
      : text("ui.chart.calendar_source");
  return (
    <>
      <NatalChartView caption={text("ui.chart.illustration")} />
      {chart.sections !== undefined && chart.sections.length > 0 ? <ChartSections chart={chart} /> : null}
      <h2>{text("ui.chart.sun")}</h2>
      <p className="lead">{chart.sun_sign ?? text("ui.chart.birth_date_missing")}</p>
      <p className="profile-meta">{source}</p>
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

function ChartSections({ chart }: { chart: ChartResponse }) {
  const sections = chart.sections ?? [];
  return (
    <>
      <nav className="section-nav editorial-list" aria-label={text("ui.chart.sections")}>
        {sections.map((section, index) => (
          <a key={section.id} className="editorial-row" href={`#chart-${section.id}`}>
            <span className="row-index" aria-hidden="true">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="row-label">{section.title}</span>
          </a>
        ))}
      </nav>
      <p className="profile-meta">{text("ui.chart.interpret")}</p>
      {sections.map((section) => (
        <section key={section.id} id={`chart-${section.id}`}>
          <h2>{section.title}</h2>
          <p>{section.body}</p>
        </section>
      ))}
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
