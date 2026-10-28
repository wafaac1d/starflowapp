import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { titled } from "../case";
import { ApiRequestError, getChart, spendStars, type ChartSection } from "../api/client";
import { natalRows } from "../api/fixtures";
import { queryKeys } from "../api/keys";
import { STAR_SILENCE, useReading } from "../readingWait";
import { Button } from "../shared/ui/Button/Button";
import { Icon } from "../shared/ui/Icon/Icon";
import { StarPrice } from "../shared/ui/StarPrice/StarPrice";
import { holdStarBalance, writeStarBalance } from "../starBalance";
import { NATAL_STARS } from "../stars";
import { Screen } from "../shared/ui/Screen/Screen";
import { Skeleton } from "../shared/ui/Skeleton/Skeleton";
import { SegmentedControl } from "../shared/ui/SegmentedControl/SegmentedControl";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import { degreeInSign } from "./format";
import { TopUpDialog } from "./TopUpDialog";
import { natalGrid, wheelPoint, type WheelAspect, type WheelBody } from "./natalWheel";
import styles from "./screens.module.css";

const PLANET = 21;

const TABS = [
  { id: "chart", label: "Карта" },
  { id: "reading", label: "Разбор" },
] as const;

export function NatalScreen() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("chart");
  const [topUp, setTopUp] = useState(false);
  const queryClient = useQueryClient();
  const chart = useQuery({ queryKey: queryKeys.chart, queryFn: () => getChart() });
  const buy = useMutation({
    mutationFn: () => spendStars({ feature: "natal" }),
    onMutate: () => holdStarBalance(queryClient, NATAL_STARS),
    onSuccess: async (ticket, _variables, restore) => {
      if (ticket.charged) {
        writeStarBalance(queryClient, ticket.balance);
      } else {
        restore?.();
      }
      await queryClient.invalidateQueries({ queryKey: queryKeys.chart });
    },
    onError: (error, _variables, restore) => {
      restore?.();
      if (error instanceof ApiRequestError && error.status === 402) {
        setTopUp(true);
      }
    },
  });
  const rows = chart.data === undefined ? [] : rowsFromChart(chart.data);
  const locked = chart.data?.natal_access === "stars_required";
  return (
    <Screen tab="today">
      <TopBar title="Натальная карта" back />
      <div className={styles.wheelFrame}>
        <img className={styles.wheel} src="/illustrations/png/natal_chart.png" alt="" />
        {chart.isSuccess && !locked ? <NatalGrid chart={chart.data} /> : null}
      </div>
      <SegmentedControl label="Вид карты" value={tab} options={TABS} onChange={setTab} />
      {chart.isPending ? <Skeleton lines={3} /> : null}
      {chart.isError ? <p role="alert">{STAR_SILENCE}</p> : null}
      {chart.isSuccess && locked ? (
        <section className={styles.reading}>
          <h2>Натальная карта</h2>
          <p>
            Одна карта стоит <StarPrice amount={NATAL_STARS} /> звёзд. С Premium она входит в период.
          </p>
          <Button loading={buy.isPending} onClick={() => buy.mutate()}>
            Открыть за <StarPrice amount={NATAL_STARS} />
          </Button>
        </section>
      ) : null}
      {chart.isSuccess && !locked && tab === "chart" ? (
        <table className={styles.table}>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <span className={styles.planet}>
                    <Icon name={row.icon} size={22} />
                    {row.title}
                  </span>
                </td>
                <td className={styles.sign}>{titled(row.sign)}</td>
                <td className={styles.degree}>{row.degree}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {chart.isSuccess && !locked && tab === "reading" ? (
        chart.data.natal_access === "allowed" ? (
          <NatalEssay sections={chart.data.sections ?? []} />
        ) : (
          <SectionList sections={chart.data.sections ?? []} />
        )
      ) : null}
      {topUp ? <TopUpDialog balance={null} onClose={() => setTopUp(false)} /> : null}
    </Screen>
  );
}

function SectionList({ sections }: { sections: ChartSection[] }) {
  return (
    <div className={styles.reading}>
      {sections.map((section) => (
        <section key={section.id}>
          <h2>{titled(section.title)}</h2>
          <p>{titled(section.body)}</p>
        </section>
      ))}
    </div>
  );
}

function NatalEssay({ sections }: { sections: ChartSection[] }) {
  const reading = useReading("natal");
  const face = reading.face;
  if (face.phase === "loading") {
    return (
      <section aria-label="Разбор" aria-busy="true">
        <Skeleton lines={8} />
      </section>
    );
  }
  if (face.phase === "ready") {
    return (
      <section className={styles.reading} aria-label="Разбор" aria-busy="false">
        {face.title !== face.body ? <h2>{titled(face.title)}</h2> : null}
        <p>{titled(face.body)}</p>
      </section>
    );
  }
  if (face.phase === "premium") {
    return <p>Разбор карты открывается на оплаченном периоде.</p>;
  }
  if (face.phase === "blocked") {
    return (
      <>
        <p role="alert">{face.body}</p>
        <SectionList sections={sections} />
      </>
    );
  }
  return (
    <>
      <p role="alert">{STAR_SILENCE}</p>
      <SectionList sections={sections} />
    </>
  );
}

function NatalGrid({ chart }: { chart: Awaited<ReturnType<typeof getChart>> | undefined }) {
  const grid = natalGrid(
    chart === undefined
      ? undefined
      : { planets: chart.planets, houseCusps: chart.house_cusps ?? null },
  );
  const byId = new Map(grid.bodies.map((body) => [body.id, body]));
  return (
    <svg className={styles.grid} viewBox="0 0 100 100" role="img" aria-label="Сетка натальной карты">
      {grid.figure.map((link) => {
        const start = wheelPoint(link.start, PLANET);
        const end = wheelPoint(link.end, PLANET);
        return (
          <line
            key={link.id}
            className={styles.figure}
            data-wheel="figure"
            x1={start.x}
            y1={start.y}
            x2={end.x}
            y2={end.y}
          />
        );
      })}
      {grid.aspects.map((aspect) => {
        const line = aspectLine(aspect, byId);
        if (line === null) {
          return null;
        }
        return (
          <line
            key={aspect.id}
            className={aspect.kind === "hard" ? styles.hardAspect : styles.softAspect}
            data-wheel={aspect.kind}
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
          />
        );
      })}
      {grid.bodies.map((body) => {
        const at = wheelPoint(body.longitude, PLANET);
        return <circle key={body.id} className={styles.planetMark} cx={at.x} cy={at.y} r={1.15} />;
      })}
    </svg>
  );
}

function aspectLine(
  aspect: WheelAspect,
  byId: Map<string, WheelBody>,
): { x1: number; y1: number; x2: number; y2: number } | null {
  const from = byId.get(aspect.from);
  const to = byId.get(aspect.to);
  if (from === undefined || to === undefined) {
    return null;
  }
  const start = wheelPoint(from.longitude, PLANET);
  const end = wheelPoint(to.longitude, PLANET);
  return { x1: start.x, y1: start.y, x2: end.x, y2: end.y };
}

function fixtureRow(index: number) {
  const row = natalRows[index];
  if (row === undefined) {
    throw new Error("natal fixture is incomplete");
  }
  return row;
}

function rowsFromChart(chart: Awaited<ReturnType<typeof getChart>> | undefined) {
  if (chart === undefined) {
    return natalRows;
  }
  const sun = chart.planets.find((planet) => planet.name.toLowerCase() === "солнце");
  const moon = chart.planets.find((planet) => planet.name.toLowerCase() === "луна");
  if (sun === undefined && chart.sun_sign === null) {
    return natalRows;
  }
  return [
    {
      id: "sun",
      icon: "planet_sun" as const,
      title: "Солнце",
      sign: sun?.sign ?? chart.sun_sign ?? fixtureRow(0).sign,
      degree: sun ? degreeInSign(sun.longitude) : fixtureRow(0).degree,
    },
    {
      id: "moon",
      icon: "planet_moon" as const,
      title: "Луна",
      sign: moon?.sign ?? chart.moon_sign ?? fixtureRow(1).sign,
      degree: moon ? degreeInSign(moon.longitude) : fixtureRow(1).degree,
    },
    {
      id: "asc",
      icon: "planet_ascendant" as const,
      title: "Асцендент",
      sign: chart.ascendant_sign ?? fixtureRow(2).sign,
      degree: fixtureRow(2).degree,
    },
  ];
}
