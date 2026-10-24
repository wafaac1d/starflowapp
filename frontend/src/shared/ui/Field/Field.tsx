import type { ReactNode } from "react";

import { Icon, type IconName } from "../Icon/Icon";
import styles from "./Field.module.css";

type FieldProps = {
  label: string;
  value: string;
  icon?: IconName;
  chevron?: boolean;
  disabled?: boolean;
  onChange?: (value: string) => void;
  children?: ReactNode;
};

export function Field({
  label,
  value,
  icon,
  chevron = true,
  disabled = false,
  onChange,
}: FieldProps) {
  return (
    <label className={disabled ? styles.disabled : styles.field}>
      <span className={styles.label}>{label}</span>
      <span className={styles.row}>
        {icon !== undefined ? <Icon name={icon} size={20} /> : null}
        <input
          className={styles.input}
          value={value}
          disabled={disabled}
          onChange={(event) => {
            onChange?.(event.target.value);
          }}
          aria-label={label}
        />
        {chevron ? <Icon name="chevron_right" size={18} /> : null}
      </span>
    </label>
  );
}
