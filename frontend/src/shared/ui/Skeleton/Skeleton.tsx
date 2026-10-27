import styles from "./Skeleton.module.css";

type SkeletonProps = {
  lines?: number;
  variant?: "lines" | "rows";
};

export function Skeleton({ lines = 3, variant = "lines" }: SkeletonProps) {
  return (
    <div className={variant === "rows" ? styles.rows : styles.block} aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <span key={index} />
      ))}
    </div>
  );
}
