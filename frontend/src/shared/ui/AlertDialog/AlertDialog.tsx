import { useEffect, useId } from "react";

import { Button } from "../Button/Button";
import { Skeleton } from "../Skeleton/Skeleton";
import styles from "./AlertDialog.module.css";

type AlertDialogProps = {
  title: string;
  body: string;
  busy?: boolean;
  dismissLabel: string;
  onDismiss: () => void;
  actionLabel?: string;
  onAction?: () => void;
};

export function AlertDialog({
  title,
  body,
  busy = false,
  dismissLabel,
  onDismiss,
  actionLabel,
  onAction,
}: AlertDialogProps) {
  const titleId = useId();
  const bodyId = useId();
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onDismiss();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [onDismiss]);
  return (
    <div
      className={styles.backdrop}
      onClick={onDismiss}
    >
      <div
        className={styles.dialog}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        aria-busy={busy}
        onClick={(event) => {
          event.stopPropagation();
        }}
      >
        <h2 id={titleId} className={styles.title}>
          {title}
        </h2>
        <div id={bodyId} className={styles.body}>
          {busy ? <Skeleton lines={3} /> : <p>{body}</p>}
        </div>
        <div className={styles.actions}>
          {actionLabel !== undefined && onAction !== undefined ? (
            <Button onClick={onAction}>{actionLabel}</Button>
          ) : null}
          <Button variant={actionLabel !== undefined ? "secondary" : "primary"} onClick={onDismiss}>
            {dismissLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
