import type { ReactNode } from "react";
import { Link } from "react-router";

import { Icon, type IconName } from "../Icon/Icon";
import styles from "./ListRow.module.css";

type ListRowProps = {
  title: string;
  subtitle?: string;
  value?: string;
  icon?: IconName;
  avatar?: string;
  chevron?: boolean;
  plain?: boolean;
  to?: string;
  onClick?: () => void;
  children?: ReactNode;
};

export function ListRow({
  title,
  subtitle,
  value,
  icon,
  avatar,
  chevron = false,
  plain = false,
  to,
  onClick,
}: ListRowProps) {
  const className = plain ? styles.plain : styles.card;
  const body = (
    <>
      {avatar !== undefined ? <span className={styles.avatar}>{avatar}</span> : null}
      {icon !== undefined ? (
        <span className={styles.icon}>
          <Icon name={icon} size={22} />
        </span>
      ) : null}
      <span className={styles.copy}>
        <span className={styles.title}>{title}</span>
        {subtitle !== undefined ? <span className={styles.subtitle}>{subtitle}</span> : null}
      </span>
      {value !== undefined ? <span className={styles.value}>{value}</span> : null}
      {chevron ? (
        <span className={styles.chevron}>
          <Icon name="chevron_right" size={18} />
        </span>
      ) : null}
    </>
  );
  if (to !== undefined) {
    return (
      <Link className={className} to={to}>
        {body}
      </Link>
    );
  }
  if (onClick !== undefined) {
    return (
      <button className={className} type="button" onClick={onClick}>
        {body}
      </button>
    );
  }
  return <div className={className}>{body}</div>;
}
