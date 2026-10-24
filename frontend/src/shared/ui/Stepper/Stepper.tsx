import { Icon } from "../Icon/Icon";
import styles from "./Stepper.module.css";

export function Stepper({ label }: { label: string }) {
  return (
    <div className={styles.stepper}>
      <Icon name="stepper_1_of_3" size={64} title={label} />
      <p className={styles.label}>{label}</p>
    </div>
  );
}
