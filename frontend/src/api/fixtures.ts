export type ForecastTopic = {
  id: string;
  title: string;
  subtitle: string;
  icon: "forecast_relationships" | "forecast_work" | "forecast_state";
};

export type PersonCard = {
  id: string;
  initials: string;
  name: string;
  birthDate: string;
  sign: string;
};

export type CompatRow = {
  id: string;
  title: string;
  subtitle: string;
  icon: "compat_dialog" | "compat_emotions" | "compat_values";
};

export type ChatLine = {
  id: string;
  role: "user" | "assistant";
  text: string;
  time: string;
};

// TODO(api): ReadingResponse has one body, not these three rows.
export const forecastTopics: ForecastTopic[] = [
  { id: "relations", title: "Отношения", subtitle: "Гармония и искренний диалог...", icon: "forecast_relationships" },
  { id: "work", title: "Работа", subtitle: "Уверенный рост и фокус...", icon: "forecast_work" },
  { id: "state", title: "Состояние", subtitle: "Спокойный эмоциональный баланс...", icon: "forecast_state" },
];

export const forecastBody =
  "Сегодня благоприятный день для важных разговоров и новых начинаний. Доверяйте интуиции — она подскажет верное направление.";

export const forecastTitle = "День для ясных решений";

// TODO(api): related entries have no separate initials field.
export const peopleFixture: PersonCard[] = [
  { id: "mama", initials: "АМ", name: "Мама", birthDate: "14.03.1968", sign: "" },
  { id: "daniil", initials: "ДП", name: "Даниил", birthDate: "22.11.1988", sign: "" },
  { id: "sergey", initials: "СЕ", name: "Сергей", birthDate: "17.06.1992", sign: "" },
];

export const ownerFixture: PersonCard = {
  id: "anna",
  initials: "А",
  name: "Анна",
  birthDate: "12.08.1995",
  sign: "Лев",
};

export const partnerFixture: PersonCard = {
  id: "mikhail",
  initials: "М",
  name: "Михаил",
  birthDate: "03.05.1993",
  sign: "Телец",
};

// TODO(api): synastry response is one text, not three titled rows.
export const compatRows: CompatRow[] = [
  { id: "dialog", title: "Диалог", subtitle: "Лёгкое и открытое общение...", icon: "compat_dialog" },
  { id: "emotions", title: "Эмоции", subtitle: "Теплота и взаимная забота...", icon: "compat_emotions" },
  { id: "values", title: "Общие ориентиры", subtitle: "Схожие цели и ценности...", icon: "compat_values" },
];

export const chatFixture: ChatLine[] = [
  { id: "user-1", role: "user", text: "На чём сосредоточиться сегодня?", time: "09:41" },
  {
    id: "bot-1",
    role: "assistant",
    text: "Сегодня важно сохранять спокойствие и не спешить с решениями. Хороший день для планирования и общения с близкими. Избегайте перегрузок.",
    time: "09:41",
  },
];

// TODO(api): chart placements do not include the profile card sentence.
export const profileTrait = "Сильная интуиция, творческий потенциал, стремление к свободе.";

export const natalRows = [
  { id: "sun", icon: "planet_sun" as const, title: "Солнце", sign: "Лев", degree: "19°24′" },
  { id: "moon", icon: "planet_moon" as const, title: "Луна", sign: "Рыбы", degree: "4°12′" },
  { id: "asc", icon: "planet_ascendant" as const, title: "Асцендент", sign: "Скорпион", degree: "12°03′" },
];

// TODO(api): there is no lunar-day copy endpoint.
export const lunarSample = {
  iso: "2025-08-12",
  phase: "Растущая Луна, 1 фаза",
  note: "Хорошее время для планов, обучения и общения.",
};

export async function getForecastTopics(): Promise<ForecastTopic[]> {
  return forecastTopics;
}

export async function getProfileTrait(): Promise<string> {
  return profileTrait;
}

export async function getCompatRows(): Promise<CompatRow[]> {
  return compatRows;
}

export async function getLunarCopy(iso: string): Promise<{ phase: string; note: string } | null> {
  if (iso === lunarSample.iso) {
    return { phase: lunarSample.phase, note: lunarSample.note };
  }
  return null;
}
