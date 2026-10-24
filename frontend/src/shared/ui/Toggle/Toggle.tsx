import styles from "./Toggle.module.css";

type ToggleProps = {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
};

export function Toggle({ label, checked, onChange }: ToggleProps) {
  return (
    <label className={styles.row}>
      <span>{label}</span>
      <input
        className={checked ? styles.on : styles.off}
        type="checkbox"
        role="switch"
        checked={checked}
        aria-checked={checked}
        onChange={(event) => {
          onChange(event.target.checked);
        }}
      />
    </label>
  );
}
