import type { IconName } from "../Icon/Icon";

const PHASES: { icon: IconName; label: string }[] = [
  { icon: "moon_phase_0_new", label: "Новолуние" },
  { icon: "moon_phase_1_waxing_crescent", label: "Растущая Луна, 1 фаза" },
  { icon: "moon_phase_2_first_quarter", label: "Первая четверть" },
  { icon: "moon_phase_3_waxing_gibbous", label: "Растущая Луна" },
  { icon: "moon_phase_4_full", label: "Полнолуние" },
  { icon: "moon_phase_5_waning_gibbous", label: "Убывающая Луна" },
  { icon: "moon_phase_6_last_quarter", label: "Последняя четверть" },
  { icon: "moon_phase_7_waning_crescent", label: "Старая Луна" },
];

const KNOWN_NEW_MOON = Date.UTC(2000, 0, 6, 18, 14);
const SYNODIC = 29.530588853;

export function phaseFor(iso: string): { icon: IconName; label: string } {
  const [year, month, day] = iso.split("-").map((part) => Number(part));
  const moment = Date.UTC(year ?? 2000, (month ?? 1) - 1, day ?? 1, 12);
  const age = ((moment - KNOWN_NEW_MOON) / 86_400_000) % SYNODIC;
  const normalized = age < 0 ? age + SYNODIC : age;
  const index = Math.floor((normalized / SYNODIC) * PHASES.length) % PHASES.length;
  const found = PHASES[index];
  if (found === undefined) {
    return { icon: "moon_phase_0_new", label: "Новолуние" };
  }
  return found;
}

export function monthLabel(year: number, month: number): string {
  const label = new Intl.DateTimeFormat("ru", { month: "long", year: "numeric" }).format(
    new Date(year, month - 1, 1),
  );
  return (label.charAt(0).toUpperCase() + label.slice(1)).replace(" г.", "");
}

export function longDate(iso: string): string {
  const [year, month, day] = iso.split("-").map((part) => Number(part));
  const label = new Intl.DateTimeFormat("ru", { day: "numeric", month: "long", year: "numeric" }).format(
    new Date(year ?? 2000, (month ?? 1) - 1, day ?? 1),
  );
  return label.replace(" г.", "");
}

export function monthGrid(year: number, month: number): Array<{ iso: string; day: number } | null> {
  const first = new Date(year, month - 1, 1);
  const lead = (first.getDay() + 6) % 7;
  const count = new Date(year, month, 0).getDate();
  const cells: Array<{ iso: string; day: number } | null> = Array.from({ length: lead }, () => null);
  for (let day = 1; day <= count; day += 1) {
    const iso = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    cells.push({ iso, day });
  }
  return cells;
}
