import { NavLink } from "react-router";

import { Icon, type IconName } from "../Icon/Icon";
import styles from "./TabBar.module.css";

export type TabId = "today" | "calendar" | "chat" | "profile";

const TABS: { id: TabId; to: string; label: string; icon: IconName; active: IconName }[] = [
  { id: "today", to: "/", label: "Сегодня", icon: "tab_today", active: "tab_today_active" },
  { id: "calendar", to: "/calendar", label: "Календарь", icon: "tab_calendar", active: "tab_calendar_active" },
  { id: "chat", to: "/chat", label: "Чат", icon: "tab_chat", active: "tab_chat_active" },
  { id: "profile", to: "/profile", label: "Профиль", icon: "tab_profile", active: "tab_profile_active" },
];

export function TabBar({ active }: { active: TabId }) {
  return (
    <nav className={styles.bar} aria-label="Разделы">
      {TABS.map((tab) => {
        const selected = tab.id === active;
        return (
          <NavLink
            key={tab.id}
            to={tab.to}
            className={(selected ? styles.active : styles.item) ?? ""}
            {...(selected ? { "aria-current": "page" as const } : {})}
          >
            <Icon name={selected ? tab.active : tab.icon} size={22} />
            <span>{tab.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
