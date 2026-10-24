import type { ReactNode } from "react";

import { Icon, type IconName } from "../Icon/Icon";
import styles from "./Button.module.css";

type ButtonProps = {
  variant?: "primary" | "secondary";
  icon?: IconName;
  disabled?: boolean;
  loading?: boolean;
  fit?: boolean;
  type?: "button" | "submit";
  onClick?: () => void;
  children: ReactNode;
};

export function Button({
  variant = "primary",
  icon,
  disabled = false,
  loading = false,
  fit = false,
  type = "button",
  onClick,
  children,
}: ButtonProps) {
  const className = [
    styles.button,
    variant === "primary" ? styles.primary : styles.secondary,
    fit ? styles.fit : "",
  ]
    .filter((item) => item !== "")
    .join(" ");
  return (
    <button
      className={className}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading}
      onClick={onClick}
    >
      {icon !== undefined ? <Icon name={icon} size={20} /> : null}
      {children}
    </button>
  );
}
