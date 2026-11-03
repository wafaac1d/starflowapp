import { useEffect, useId, type ReactNode } from "react";

import { Button } from "../Button/Button";
import { Icon, type IconName } from "../Icon/Icon";
import styles from "./Dialog.module.css";

type DialogProps = {
  title: string;
  subtitle?: ReactNode;
  badge?: string;
  icon?: IconName;
  imageSrc?: string;
  busy?: boolean;
  role?: "dialog" | "alertdialog";
  onClose: () => void;
  children?: ReactNode;
  actions?: ReactNode;
};

export function Dialog({
  title,
  subtitle,
  badge,
  icon = "profile_trait_sparkle",
  imageSrc,
  busy = false,
  role = "dialog",
  onClose,
  children,
  actions,
}: DialogProps) {
  const titleId = useId();
  const bodyId = useId();
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);
  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div
        className={styles.dialog}
        role={role}
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        aria-busy={busy}
        onClick={(event) => {
          event.stopPropagation();
        }}
      >
        <div className={styles.head}>
          {imageSrc !== undefined ? (
            <img className={styles.image} src={imageSrc} alt="" />
          ) : (
            <span className={styles.mark}>
              <Icon name={icon} size={36} />
            </span>
          )}
          <div className={styles.copy}>
            <div className={styles.titleRow}>
              <h2 id={titleId} className={styles.title}>
                {title}
              </h2>
              {badge !== undefined ? <span className={styles.badge}>{badge}</span> : null}
            </div>
            {subtitle !== undefined ? <div className={styles.subtitle}>{subtitle}</div> : null}
          </div>
        </div>
        <div id={bodyId} className={styles.body}>
          {children}
        </div>
        <div className={styles.actions}>
          {actions}
          <Button variant={actions !== undefined ? "secondary" : "primary"} onClick={onClose}>
            Понятно
          </Button>
        </div>
      </div>
    </div>
  );
}
