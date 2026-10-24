import type { ReactNode } from "react";

import { TabBar, type TabId } from "../TabBar/TabBar";
import styles from "./Screen.module.css";

type ScreenProps = {
  tab?: TabId;
  children: ReactNode;
};

export function Screen({ tab, children }: ScreenProps) {
  return (
    <div className={tab !== undefined ? styles.withTab : styles.plain}>
      {children}
      {tab !== undefined ? <TabBar active={tab} /> : null}
    </div>
  );
}
