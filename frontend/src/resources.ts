import { texts, type TextKey } from "./generated/texts";

export type { TextKey };

export const homeCopy = {
  title: texts["ui.home.title"],
  lead: texts["ui.home.lead"],
  disclaimer: texts["ui.home.disclaimer"],
  action: texts["ui.home.action"],
  status_ready: texts["ui.home.status_ready"],
  status_failed: texts["ui.home.status_failed"],
  logo_label: texts["ui.home.logo_label"],
  price_label: texts["ui.home.price_label"],
};

export function text(key: TextKey): string {
  return texts[key];
}

export function formatText(key: TextKey, values: Record<string, string>): string {
  let rendered: string = texts[key];
  for (const [name, value] of Object.entries(values)) {
    rendered = rendered.replaceAll(`{${name}}`, value);
  }
  return rendered;
}

export function pluralText(key: "ui.premium.questions", count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  let form: "one" | "few" | "many" = "many";
  if (mod10 === 1 && mod100 !== 11) {
    form = "one";
  } else if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    form = "few";
  }
  const full = `${key}.${form}` as TextKey;
  return formatText(full, { count: String(count) });
}
