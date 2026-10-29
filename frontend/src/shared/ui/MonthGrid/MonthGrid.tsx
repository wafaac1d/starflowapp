import { Icon } from "../Icon/Icon";
import { monthGrid, monthLabel } from "../LunarCalendar/phase";
import styles from "./MonthGrid.module.css";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

type MonthGridProps = {
  year: number;
  month: number;
  selected: string;
  marks: ReadonlySet<string>;
  onSelect: (iso: string) => void;
  onPrevious: () => void;
  onNext: () => void;
};

export function MonthGrid({
  year,
  month,
  selected,
  marks,
  onSelect,
  onPrevious,
  onNext,
}: MonthGridProps) {
  const cells = monthGrid(year, month);
  return (
    <section className={styles.month} aria-label="Календарь">
      <div className={styles.nav}>
        <button type="button" aria-label="Предыдущий месяц" onClick={onPrevious}>
          <Icon name="chevron_left" size={20} />
        </button>
        <h2>{monthLabel(year, month)}</h2>
        <button type="button" aria-label="Следующий месяц" onClick={onNext}>
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
          const marked = marks.has(cell.iso);
          const active = cell.iso === selected;
          const name = marked ? `${cell.day}, благоприятный день` : String(cell.day);
          return (
            <button
              key={cell.iso}
              type="button"
              className={active ? styles.active : styles.day}
              aria-label={name}
              aria-pressed={active}
              onClick={() => {
                onSelect(cell.iso);
              }}
            >
              <span>{cell.day}</span>
              {marked ? <span className={styles.dot} /> : <span className={styles.spacer} />}
            </button>
          );
        })}
      </div>
    </section>
  );
}
