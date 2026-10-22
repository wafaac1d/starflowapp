export type AlmanacDay = {
  iso: string;
  day: number;
  weekday: string;
  weekdayShort: string;
  month: string;
};

export function isoInZone(moment: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(moment);
}

export function describeIso(iso: string, timeZone: string): AlmanacDay {
  const moment = utcNoon(iso);
  const weekday = new Intl.DateTimeFormat("ru", { timeZone, weekday: "long" }).format(moment);
  const weekdayShort = new Intl.DateTimeFormat("ru", { timeZone, weekday: "short" }).format(moment);
  const month = new Intl.DateTimeFormat("ru", { timeZone, month: "long" }).format(moment);
  const day = Number(
    new Intl.DateTimeFormat("ru", { timeZone, day: "numeric" }).format(moment),
  );
  return { iso, day, weekday, weekdayShort, month };
}

export function monthDays(iso: string, timeZone: string): AlmanacDay[] {
  const [yearText, monthText] = iso.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const count = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const days: AlmanacDay[] = [];
  for (let day = 1; day <= count; day += 1) {
    const next = `${yearText}-${monthText}-${String(day).padStart(2, "0")}`;
    days.push(describeIso(next, timeZone));
  }
  return days;
}

export function shiftMonth(iso: string, delta: number): string {
  const [yearText, monthText] = iso.split("-");
  const cursor = new Date(Date.UTC(Number(yearText ?? "1970"), Number(monthText ?? "1") - 1 + delta, 1, 12));
  const year = cursor.getUTCFullYear();
  const month = String(cursor.getUTCMonth() + 1).padStart(2, "0");
  return `${year}-${month}-01`;
}

function utcNoon(iso: string): Date {
  const [year, month, day] = iso.split("-").map((part) => Number(part));
  return new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1, 12));
}
