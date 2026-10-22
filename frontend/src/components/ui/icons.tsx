import type { CSSProperties } from "react";

const ICONS = {
  sun: "/icons/sun.svg",
  calendar: "/icons/calendar.svg",
  people: "/icons/people.svg",
  profile: "/icons/profile.svg",
  "arrow-right": "/icons/arrow-right.svg",
  "arrow-left": "/icons/arrow-left.svg",
  moon: "/icons/moon.svg",
  history: "/icons/history.svg",
  "natal-chart": "/icons/natal-chart.svg",
  premium: "/icons/premium.svg",
  gift: "/icons/gift.svg",
  close: "/icons/close.svg",
  chat: "/icons/chat.svg",
  bookmark: "/icons/bookmark.svg",
  settings: "/icons/settings.svg",
  share: "/icons/share.svg",
} as const;

export type IconName = keyof typeof ICONS;

type IconProps = {
  name: IconName;
};

export function Icon({ name }: IconProps) {
  const style = { "--icon": `url("${ICONS[name]}")` } as CSSProperties;
  return <span className="icon" style={style} aria-hidden="true" />;
}

export const illustrationCream = "/illustrations/three-circles-cream.svg";
export const illustrationWine = "/illustrations/three-circles-wine.svg";
