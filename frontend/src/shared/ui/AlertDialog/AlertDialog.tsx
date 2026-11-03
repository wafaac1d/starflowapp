import type { ReactNode } from "react";

import { Button } from "../Button/Button";
import { Dialog } from "../Dialog/Dialog";
import type { IconName } from "../Icon/Icon";
import { StarLink } from "../StarLink/StarLink";

type AlertDialogProps = {
  title: string;
  body: string;
  busy?: boolean;
  icon?: IconName;
  onDismiss: () => void;
  actionLabel?: string;
  onAction?: () => void;
};

export function AlertDialog({
  title,
  body,
  busy = false,
  icon,
  onDismiss,
  actionLabel,
  onAction,
}: AlertDialogProps) {
  const action: ReactNode =
    actionLabel !== undefined && onAction !== undefined ? (
      <Button onClick={onAction}>{actionLabel}</Button>
    ) : undefined;
  return (
    <Dialog
      title={title}
      role="alertdialog"
      busy={busy}
      onClose={onDismiss}
      {...(icon !== undefined ? { icon } : {})}
      {...(action !== undefined ? { actions: action } : {})}
    >
      {busy ? <StarLink /> : <p>{body}</p>}
    </Dialog>
  );
}
