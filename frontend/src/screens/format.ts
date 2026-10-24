export function greeting(date: Date): string {
  const hour = date.getHours();
  if (hour < 6) {
    return "Доброй ночи,";
  }
  if (hour < 12) {
    return "Доброе утро,";
  }
  if (hour < 18) {
    return "Добрый день,";
  }
  return "Добрый вечер,";
}

export function formatRuDate(date: Date): string {
  return new Intl.DateTimeFormat("ru", {
    day: "numeric",
    month: "long",
    year: "numeric",
  })
    .format(date)
    .replace(" г.", "");
}

const KNOWN_INITIALS: Record<string, string> = {
  Мама: "АМ",
  Даниил: "ДП",
  Сергей: "СЕ",
  Анна: "А",
  Михаил: "М",
};

export function initialsOf(name: string, override?: string): string {
  if (override !== undefined && override !== "") {
    return override;
  }
  const known = KNOWN_INITIALS[name];
  if (known !== undefined) {
    return known;
  }
  const parts = name.trim().split(/\s+/).filter((part) => part !== "");
  const first = parts[0];
  const second = parts[1];
  if (first !== undefined && second !== undefined) {
    return `${first.charAt(0)}${second.charAt(0)}`.toUpperCase();
  }
  return name.replace(/\s+/g, "").slice(0, 2).toUpperCase();
}

export function degreeInSign(longitude: number): string {
  const within = ((longitude % 30) + 30) % 30;
  const degrees = Math.floor(within);
  const minutes = Math.round((within - degrees) * 60);
  return `${degrees}°${String(minutes).padStart(2, "0")}′`;
}
