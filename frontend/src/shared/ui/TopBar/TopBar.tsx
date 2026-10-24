import type { ReactNode } from "react";
import { useNavigate } from "react-router";

import { Icon } from "../Icon/Icon";
import styles from "./TopBar.module.css";

type TopBarProps = {
  title?: string;
  align?: "center" | "left";
  back?: boolean;
  trailing?: ReactNode;
};

export function TopBar({ title, align = "center", back = false, trailing }: TopBarProps) {
  const navigate = useNavigate();
  return (
    <header className={align === "left" ? styles.left : styles.center}>
      {back ? (
        <button
          type="button"
          className={styles.back}
          aria-label="назад"
          onClick={() => {
            void navigate(-1);
          }}
        >
          <Icon name="arrow_back" size={22} />
        </button>
      ) : align === "center" ? (
        <span className={styles.spacer} />
      ) : null}
      {title !== undefined ? <h1 className={styles.title}>{title}</h1> : <span />}
      <span className={styles.trailing}>{trailing}</span>
    </header>
  );
}
