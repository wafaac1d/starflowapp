import { useEffect, useRef, type FormEvent, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router";

import type { AlmanacDay } from "../../almanacDate";
import { titled } from "../../case";
import { text, type TextKey } from "../../resources";
import type { ThemeChoice } from "../../theme";
import { Icon, illustrationCream, type IconName } from "./icons";

export function Divider() {
  return <hr className="rule" />;
}

type RowProps = {
  index?: string;
  label: string;
  hint?: string;
  icon?: IconName;
  typed?: boolean;
  onClick?: () => void;
  arrow?: boolean;
};

export function EditorialListRow({
  index,
  label,
  hint,
  icon,
  typed = false,
  onClick,
  arrow = false,
}: RowProps) {
  const body = (
    <>
      {icon !== undefined ? <Icon name={icon} /> : null}
      {index !== undefined ? (
        <span className="row-index" aria-hidden="true">
          {index}
        </span>
      ) : null}
      <span className="row-copy">
        <span className={typed ? "row-label as-typed" : "row-label"}>{label}</span>
        {hint !== undefined && hint !== "" ? <span className="row-hint">{hint}</span> : null}
      </span>
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

const PROFILE_TAB = new Set(["/settings", "/delete"]);

export function BottomNavigation() {
  const location = useLocation();
  return (
    <nav className="tabbar" aria-label={text("ui.nav.label")}>
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end === true}
          className={({ isActive }) => {
            const active = tab.to === "/profile" ? isActive || PROFILE_TAB.has(location.pathname) : isActive;
            return active ? "tab tab-active" : "tab";
          }}
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

export function PageHeader({ title, backTo }: { title: string; backTo?: string }) {
  const navigate = useNavigate();
  return (
    <header className="page-head">
      {backTo !== undefined ? (
        <button
          type="button"
          className="icon-button"
          aria-label={text("ui.common.back")}
          onClick={() => {
            const state = window.history.state as { idx?: number } | null;
            if (state !== null && typeof state.idx === "number" && state.idx > 0) {
              void navigate(-1);
              return;
            }
            void navigate(backTo);
          }}
        >
          <Icon name="arrow-left" />
        </button>
      ) : null}
      <h1 className="page-title">{title}</h1>
    </header>
  );
}

export function ProfileSummary({
  name,
  sign,
  premium,
}: {
  name: string;
  sign: string | null;
  premium: boolean;
}) {
  const parts = [sign === null ? null : titled(sign), premium ? text("ui.profile.premium_on") : null].filter(
    (part): part is string => part !== null && part !== "",
  );
  return (
    <div className="profile-summary">
      <p className="profile-name as-typed">{name}</p>
      {parts.length > 0 ? <p className="profile-meta">{parts.join(" · ")}</p> : null}
    </div>
  );
}

const PERIODS: { id: "day" | "week" | "month"; label: TextKey }[] = [
  { id: "day", label: "ui.reading.period_day" },
  { id: "week", label: "ui.reading.period_week" },
  { id: "month", label: "ui.reading.period_month" },
];

export function PeriodTabs({
  value,
  onChange,
}: {
  value: "day" | "week" | "month";
  onChange: (value: "day" | "week" | "month") => void;
}) {
  return (
    <div className="segment" role="tablist" aria-label={text("ui.reading.day")}>
      {PERIODS.map((item) => {
        const selected = value === item.id;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={selected}
            className={selected ? "segment-item segment-item-active" : "segment-item"}
            onClick={() => {
              onChange(item.id);
            }}
          >
            {text(item.label)}
          </button>
        );
      })}
    </div>
  );
}

const THEME_OPTIONS: { id: ThemeChoice; label: TextKey }[] = [
  { id: "telegram", label: "ui.theme.telegram" },
  { id: "light", label: "ui.theme.light" },
  { id: "dark", label: "ui.theme.dark" },
];

export function ThemeSelector({
  value,
  onChange,
}: {
  value: ThemeChoice;
  onChange: (value: ThemeChoice) => void;
}) {
  return (
    <div className="segment" role="radiogroup" aria-label={text("ui.settings.appearance")}>
      {THEME_OPTIONS.map((item) => {
        const selected = value === item.id;
        return (
          <button
            key={item.id}
            type="button"
            role="radio"
            aria-checked={selected}
            className={selected ? "segment-item segment-item-active" : "segment-item"}
            onClick={() => {
              onChange(item.id);
            }}
          >
            {text(item.label)}
          </button>
        );
      })}
    </div>
  );
}

export function Switch({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="switch-row">
      <span>{label}</span>
      <input
        className="switch"
        type="checkbox"
        checked={checked}
        onChange={(event) => {
          onChange(event.target.checked);
        }}
      />
    </label>
  );
}

export function CompatibilityEntry({
  title,
  lead,
  onClick,
}: {
  title: string;
  lead: string;
  onClick: () => void;
}) {
  return (
    <button type="button" className="compat-entry" onClick={onClick}>
      <span className="row-copy">
        <span className="compat-title">{title}</span>
        <span className="compat-lead">{lead}</span>
      </span>
      <Icon name="arrow-right" />
    </button>
  );
}

export function ChatMessage({ role, content }: { role: string; content: string }) {
  return <p className={role === "user" ? "chat-user" : "chat-reply"}>{content}</p>;
}

export function ChatComposer({
  value,
  pending,
  onChange,
  onSubmit,
}: {
  value: string;
  pending: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}) {
  const field = useRef<HTMLTextAreaElement>(null);
  const tooLong = value.length > 500;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (value.trim() === "" || tooLong || pending) {
      return;
    }
    onSubmit();
  };
  return (
    <form className="chat-dock" onSubmit={submit}>
      <label className="visually-hidden" htmlFor="assistant-question">
        {text("ui.assistant.title")}
      </label>
      <div className="composer">
        <textarea
          ref={field}
          id="assistant-question"
          className="chat-input"
          placeholder={text("ui.assistant.placeholder")}
          value={value}
          maxLength={500}
          rows={1}
          onChange={(event) => {
            onChange(event.target.value);
            const node = event.target;
            node.style.height = "auto";
            node.style.height = `${Math.min(node.scrollHeight, 120)}px`;
          }}
        />
        <button
          className="send-button"
          type="submit"
          aria-label={text("ui.assistant.send")}
          disabled={value.trim() === "" || tooLong || pending}
        >
          <Icon name="arrow-right" />
        </button>
      </div>
    </form>
  );
}

export function NatalChartView({ caption }: { caption: string }) {
  return (
    <figure className="natal-mark">
      <Icon name="natal-chart" />
      <figcaption>{caption}</figcaption>
    </figure>
  );
}
