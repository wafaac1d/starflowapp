import { Icon } from "../Icon/Icon";
import { monthGrid, monthLabel, phaseFor } from "./phase";
import styles from "./LunarCalendar.module.css";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

type LunarCalendarProps = {
  year: number;
  month: number;
  selected: string;
  onSelect: (iso: string) => void;
  onPrevious: () => void;
  onNext: () => void;
};

export function LunarCalendar({
  year,
  month,
  selected,
  onSelect,
  onPrevious,
  onNext,
}: LunarCalendarProps) {
  const cells = monthGrid(year, month);
  return (
    <section aria-label="лунный календарь">
      <div className={styles.nav}>
        <button type="button" aria-label="предыдущий месяц" onClick={onPrevious}>
          <Icon name="chevron_left" size={20} />
        </button>
        <h2>{monthLabel(year, month)}</h2>
        <button type="button" aria-label="следующий месяц" onClick={onNext}>
          <Icon name="chevron_right" size={20} />
        </button>
      </div>
      <div className={styles.week}>
        {WEEKDAYS.map((day) => (
          <span key={day}>{day}</span>
        ))}
      </div>
      <div className={styles.grid}>
        {cells.map((cell, index) => {
          if (cell === null) {
            return <span key={`empty-${index}`} />;
          }
          const phase = phaseFor(cell.iso);
          const active = cell.iso === selected;
          return (
            <button
              key={cell.iso}
              type="button"
              className={active ? styles.active : styles.day}
              aria-pressed={active}
              onClick={() => {
                onSelect(cell.iso);
              }}
            >
              <span>{cell.day}</span>
              <Icon name={phase.icon} size={14} />
            </button>
          );
        })}
      </div>
    </section>
  );
}
