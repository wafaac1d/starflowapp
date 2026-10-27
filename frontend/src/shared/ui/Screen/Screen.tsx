import type { ReactNode } from "react";

import { TabBar, type TabId } from "../TabBar/TabBar";
import styles from "./Screen.module.css";

type ScreenProps = {
  tab?: TabId;
  fit?: boolean;
  children: ReactNode;
};

export function Screen({ tab, fit = false, children }: ScreenProps) {
  const pinned = tab !== undefined;
  const className = [pinned ? styles.withTab : styles.plain, fit ? styles.fit : ""].filter(Boolean).join(" ");
  return (
    <div className={className}>
      {children}
      {pinned ? <TabBar active={tab} /> : null}
    </div>
  );
}
