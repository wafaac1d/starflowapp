import arrowLeft from "../../../../static/icons/svg/arrow-left.svg";
import arrowRight from "../../../../static/icons/svg/arrow-right.svg";
import bookmark from "../../../../static/icons/svg/bookmark.svg";
import calendar from "../../../../static/icons/svg/calendar.svg";
import chat from "../../../../static/icons/svg/chat.svg";
import close from "../../../../static/icons/svg/close.svg";
import gift from "../../../../static/icons/svg/gift.svg";
import history from "../../../../static/icons/svg/history.svg";
import moon from "../../../../static/icons/svg/moon.svg";
import natalChart from "../../../../static/icons/svg/natal-chart.svg";
import people from "../../../../static/icons/svg/people.svg";
import premium from "../../../../static/icons/svg/premium.svg";
import profile from "../../../../static/icons/svg/profile.svg";
import settings from "../../../../static/icons/svg/settings.svg";
import share from "../../../../static/icons/svg/share.svg";
import sun from "../../../../static/icons/svg/sun.svg";

const ICONS = {
  sun,
  calendar,
  people,
  profile,
  "arrow-right": arrowRight,
  "arrow-left": arrowLeft,
  moon,
  history,
  "natal-chart": natalChart,
  premium,
  gift,
  close,
  chat,
  bookmark,
  settings,
  share,
} as const;

export type IconName = keyof typeof ICONS;

type IconProps = {
  name: IconName;
};

export function Icon({ name }: IconProps) {
  return <img className="icon" src={ICONS[name]} alt="" />;
}

export const illustrationCream = "/illustrations/three-circles-cream.svg";
export const illustrationWine = "/illustrations/three-circles-wine.svg";
