import { useRef } from "react";

import styles from "./SegmentedControl.module.css";

type Segment<T extends string> = {
  id: T;
  label: string;
};

type SegmentedControlProps<T extends string> = {
  label: string;
  value: T;
  options: readonly Segment<T>[];
  onChange: (value: T) => void;
  role?: "tablist" | "radiogroup";
};

export function SegmentedControl<T extends string>({
  label,
  value,
  options,
  onChange,
  role = "tablist",
}: SegmentedControlProps<T>) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const index = Math.max(
    0,
    options.findIndex((item) => item.id === value),
  );
  const move = (next: number) => {
    const option = options[next];
    if (option === undefined) {
      return;
    }
    onChange(option.id);
    refs.current[next]?.focus();
  };
  return (
    <div className={styles.track} role={role} aria-label={label}>
      {options.map((option, optionIndex) => {
        const selected = option.id === value;
        return (
          <button
            key={option.id}
            ref={(node) => {
              refs.current[optionIndex] = node;
            }}
            type="button"
            role={role === "tablist" ? "tab" : "radio"}
            aria-selected={role === "tablist" ? selected : undefined}
            aria-checked={role === "radiogroup" ? selected : undefined}
            tabIndex={selected || (value === "" && optionIndex === 0) ? 0 : -1}
            className={selected ? styles.active : styles.item}
            onClick={() => {
              onChange(option.id);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowRight") {
                event.preventDefault();
                move(Math.min(options.length - 1, index + 1));
              }
              if (event.key === "ArrowLeft") {
                event.preventDefault();
                move(Math.max(0, index - 1));
              }
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
