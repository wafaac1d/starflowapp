import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getChart } from "../api/client";
import { natalRows } from "../api/fixtures";
import { queryKeys } from "../api/keys";
import { Icon } from "../shared/ui/Icon/Icon";
import { Screen } from "../shared/ui/Screen/Screen";
import { SegmentedControl } from "../shared/ui/SegmentedControl/SegmentedControl";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import { degreeInSign } from "./format";
import { natalGrid, wheelPoint, type WheelAspect, type WheelBody } from "./natalWheel";
import styles from "./screens.module.css";

const HUB = 4.5;
const INNER = 27.2;
const PLANET = 21;

const TABS = [
  { id: "chart", label: "Карта" },
  { id: "reading", label: "Разбор" },
] as const;

export function NatalScreen() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("chart");
  const chart = useQuery({ queryKey: queryKeys.chart, queryFn: () => getChart() });
  const rows = rowsFromChart(chart.data);
  return (
    <Screen tab="today">
      <TopBar title="Натальная карта" back />
      <div className={styles.wheelFrame}>
        <img className={styles.wheel} src="/illustrations/png/natal_chart.png" alt="" />
        <NatalGrid chart={chart.data} />
      </div>
      <SegmentedControl label="вид карты" value={tab} options={TABS} onChange={setTab} />
      {tab === "chart" ? (
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
                <td className={styles.sign}>{row.sign}</td>
                <td className={styles.degree}>{row.degree}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className={styles.stack}>
          {(chart.data?.sections ?? []).map((section) => (
            <section key={section.id}>
              <h2>{section.title}</h2>
              <p>{section.body}</p>
            </section>
          ))}
        </div>
      )}
    </Screen>
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
      {grid.cusps.map((longitude, index) => {
        const inner = wheelPoint(longitude, HUB);
        const outer = wheelPoint(longitude, INNER);
        return (
          <line
            key={`house-${index}`}
            className={styles.houseSpoke}
            data-wheel="house"
            x1={inner.x}
            y1={inner.y}
            x2={outer.x}
            y2={outer.y}
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
