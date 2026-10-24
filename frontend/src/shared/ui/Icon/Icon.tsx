import type { CSSProperties } from "react";

import { iconNames, type IconName } from "./iconNames";
import styles from "./Icon.module.css";

export type { IconName };

const MULTICOLOR = new Set<IconName>([
  "assistant_avatar",
  "forecast_state",
  "forecast_work",
  "planet_moon",
  "profile_trait_sparkle",
  "send",
  "stepper_1_of_3",
  "user_circle",
  ...iconNames.filter(
    (name) =>
      name.startsWith("moon_phase_") ||
      name.startsWith("premium_") ||
      name.startsWith("compat_") ||
      name.startsWith("toggle_"),
  ),
]);

type IconProps = {
  name: IconName;
  size?: number;
  title?: string;
};

export function isMulticolorIcon(name: IconName): boolean {
  return MULTICOLOR.has(name);
}

export function Icon({ name, size = 24, title }: IconProps) {
  const label = title === undefined ? undefined : title;
  if (isMulticolorIcon(name)) {
    return (
      <img
        className={styles.image}
        src={`/icons/svg/${name}.svg`}
        width={size}
        height={size}
        alt={label ?? ""}
        aria-hidden={label === undefined}
      />
    );
  }
  const style = {
    width: size,
    height: size,
    maskImage: `url("/icons/svg/${name}.svg")`,
    WebkitMaskImage: `url("/icons/svg/${name}.svg")`,
  } as CSSProperties;
  if (label === undefined) {
    return <span className={styles.mask} style={style} aria-hidden="true" />;
  }
  return <span className={styles.mask} style={style} role="img" aria-label={label} />;
}
