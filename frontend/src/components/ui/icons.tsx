const ICONS = {
  sun: "/icons/svg/planet_sun.svg",
  calendar: "/icons/svg/tab_calendar.svg",
  people: "/icons/svg/user_add.svg",
  profile: "/icons/svg/tab_profile.svg",
  "arrow-right": "/icons/svg/chevron_right.svg",
  "arrow-left": "/icons/svg/arrow_back.svg",
  moon: "/icons/svg/planet_moon.svg",
  history: "/icons/svg/save_bookmark.svg",
  "natal-chart": "/icons/svg/premium_natal_chart.svg",
  premium: "/icons/svg/stars_currency.svg",
  gift: "/icons/svg/stars_currency.svg",
  close: "/icons/svg/chevron_left.svg",
  chat: "/icons/svg/tab_chat.svg",
  bookmark: "/icons/svg/save_bookmark.svg",
  settings: "/icons/svg/gear.svg",
  share: "/icons/svg/share.svg",
} as const;

export type IconName = keyof typeof ICONS;

export function Icon({ name }: { name: IconName }) {
  return <img className="icon" src={ICONS[name]} alt="" />;
}

export const illustrationCream = "/illustrations/png/home_moon_orbits.png";
export const illustrationWine = "/illustrations/png/onboarding_eclipse.png";
