import styles from "./Avatar.module.css";

type AvatarProps = {
  letters: string;
  size?: "s" | "m" | "l";
};

export function Avatar({ letters, size = "m" }: AvatarProps) {
  const className = size === "l" ? styles.l : size === "s" ? styles.s : styles.m;
  return <span className={className}>{letters}</span>;
}
