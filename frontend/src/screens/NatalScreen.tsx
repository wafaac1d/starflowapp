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
import styles from "./screens.module.css";

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
      <img className={styles.wheel} src="/illustrations/png/natal_chart.png" alt="" />
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
