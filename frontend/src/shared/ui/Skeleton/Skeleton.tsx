import styles from "./Skeleton.module.css";

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className={styles.block} aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <span key={index} />
      ))}
    </div>
  );
}
