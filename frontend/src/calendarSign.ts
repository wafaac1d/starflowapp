const STARTS: readonly (readonly [number, number, string])[] = [
  [1, 20, "водолей"],
  [2, 19, "рыбы"],
  [3, 21, "овен"],
  [4, 20, "телец"],
  [5, 21, "близнецы"],
  [6, 21, "рак"],
  [7, 23, "лев"],
  [8, 23, "дева"],
  [9, 23, "весы"],
  [10, 23, "скорпион"],
  [11, 22, "стрелец"],
  [12, 22, "козерог"],
];

/** Календарная подпись знака. Те же границы, что у расчёта профиля. */
export function calendarSign(value: string): string | null {
  const parsed = readDate(value);
  if (parsed === null) {
    return null;
  }
  let chosen = "козерог";
  for (const [month, day, name] of STARTS) {
    if (parsed.month > month || (parsed.month === month && parsed.day >= day)) {
      chosen = name;
    }
  }
  return chosen;
}

export function displayBirthDate(value: string): string {
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (iso === null) {
    return value;
  }
  const year = iso[1];
  const month = iso[2];
  const day = iso[3];
  if (year === undefined || month === undefined || day === undefined) {
    return value;
  }
  return `${day}.${month}.${year}`;
}

function readDate(value: string): { month: number; day: number } | null {
  const trimmed = value.trim();
  const dotted = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(trimmed);
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  const day = Number(dotted?.[1] ?? iso?.[3]);
  const month = Number(dotted?.[2] ?? iso?.[2]);
  if (dotted === null && iso === null) {
    return null;
  }
  if (
    !Number.isInteger(day) ||
    !Number.isInteger(month) ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > 31
  ) {
    return null;
  }
  return { month, day };
}
