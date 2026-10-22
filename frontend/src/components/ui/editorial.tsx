import { useEffect, type ReactNode } from "react";
import { NavLink } from "react-router";

import type { AlmanacDay } from "../../almanacDate";
import { text, type TextKey } from "../../resources";
import { Icon, illustrationCream, type IconName } from "./icons";

export function Divider() {
  return <hr className="rule" />;
}

type RowProps = {
  index?: string;
  label: string;
  onClick?: () => void;
  arrow?: boolean;
};

export function EditorialListRow({ index, label, onClick, arrow = false }: RowProps) {
  const body = (
    <>
      {index !== undefined ? <span className="row-index">{index}</span> : null}
      <span className="row-label">{label}</span>
      {arrow ? <Icon name="arrow-right" /> : null}
    </>
  );
  if (onClick === undefined) {
    return <div className="editorial-row">{body}</div>;
  }
  return (
    <button type="button" className="editorial-row" onClick={onClick}>
      {body}
    </button>
  );
}

type DateHeroProps = {
  month: string;
  weekday: string;
  day: number;
  lineOne: string;
  lineTwo: string;
};

export function DateHero({ month, weekday, day, lineOne, lineTwo }: DateHeroProps) {
  return (
    <section className="date-hero" aria-label={`${day} ${month}, ${weekday}`}>
      <p className="date-kicker">
        {month} / {weekday}
      </p>
      <p className="date-number" aria-hidden="true">
        {day}
      </p>
      <p className="date-phrase">
        {lineOne}
        <br />
        {lineTwo}
      </p>
    </section>
  );
}

type WeekProps = {
  days: AlmanacDay[];
  selected: string;
  onSelect: (iso: string) => void;
};

export function WeekDaySelector({ days, selected, onSelect }: WeekProps) {
  useEffect(() => {
    const node = document.querySelector<HTMLElement>(".week-day-active");
    if (node !== null && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ inline: "center", block: "nearest" });
    }
  }, [selected]);
  return (
    <div className="week-strip" role="listbox" aria-label={text("ui.calendar.strip")}>
      {days.map((item) => {
        const active = item.iso === selected;
        return (
          <button
            key={item.iso}
            type="button"
            role="option"
            aria-selected={active}
            className={active ? "week-day week-day-active" : "week-day"}
            onClick={() => {
              onSelect(item.iso);
            }}
          >
            <span>{item.weekdayShort}</span>
            <strong>{item.day}</strong>
          </button>
        );
      })}
    </div>
  );
}

type Marker = "circle" | "square" | "triangle";

type TimelineProps = {
  marker: Marker;
  title: string;
  body: string;
  onClick: () => void;
};

export function TimelineItem({ marker, title, body, onClick }: TimelineProps) {
  return (
    <button type="button" className="timeline-item" onClick={onClick}>
      <MarkerShape marker={marker} />
      <span>
        <span className="timeline-title">{title}</span>
        <span className="timeline-body">{body}</span>
      </span>
    </button>
  );
}

function MarkerShape({ marker }: { marker: Marker }) {
  if (marker === "square") {
    return (
      <svg className="marker" viewBox="0 0 16 16" aria-hidden="true">
        <rect x="2.75" y="2.75" width="10.5" height="10.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    );
  }
  if (marker === "triangle") {
    return (
      <svg className="marker" viewBox="0 0 16 16" aria-hidden="true">
        <path d="M8 2.8 13.4 13.2H2.6L8 2.8Z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    );
  }
  return (
    <svg className="marker" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="5.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

type HeroProps = {
  kicker: string;
  title: string;
  lead: string;
};

export function PremiumHero({ kicker, title, lead }: HeroProps) {
  return (
    <section className="premium-hero">
      <p className="hero-kicker">{kicker}</p>
      <h1 className="hero-title">{title}</h1>
      <p className="hero-lead">{lead}</p>
      <img className="hero-art" src={illustrationCream} alt="" aria-hidden="true" />
    </section>
  );
}

const TABS: { to: string; label: TextKey; icon: IconName; end?: boolean }[] = [
  { to: "/", label: "ui.nav.today", icon: "sun", end: true },
  { to: "/calendar", label: "ui.nav.calendar", icon: "calendar" },
  { to: "/related", label: "ui.nav.people", icon: "people" },
  { to: "/profile", label: "ui.nav.profile", icon: "profile" },
];

export function BottomNavigation() {
  return (
    <nav className="tabbar" aria-label={text("ui.nav.label")}>
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end === true}
          className={({ isActive }) => (isActive ? "tab tab-active" : "tab")}
        >
          <Icon name={tab.icon} />
          <span>{text(tab.label)}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export function WineStatement({ kicker, children }: { kicker: string; children: ReactNode }) {
  return (
    <section className="wine-panel">
      <p className="hero-kicker">{kicker}</p>
      <div className="wine-copy">{children}</div>
      <svg className="wine-arc" viewBox="0 0 140 90" aria-hidden="true">
        <path d="M8 82C28 28 96 8 136 36" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </section>
  );
}
