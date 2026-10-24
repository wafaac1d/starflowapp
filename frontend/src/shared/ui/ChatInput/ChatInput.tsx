import { Icon } from "../Icon/Icon";
import styles from "./ChatInput.module.css";

type ChatInputProps = {
  value: string;
  pending?: boolean;
  locked?: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function ChatInput({ value, pending = false, locked = false, onChange, onSubmit }: ChatInputProps) {
  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        if (locked || value.trim() === "" || pending) {
          return;
        }
        onSubmit();
      }}
    >
      <input
        className={styles.input}
        value={value}
        placeholder="Написать сообщение…"
        aria-label="Написать сообщение…"
        disabled={locked}
        onChange={(event) => {
          if (locked) {
            return;
          }
          onChange(event.target.value);
        }}
      />
      <button className={styles.send} type="submit" aria-label="Отправить" disabled={locked || pending || value.trim() === ""}>
        <Icon name="send" size={36} />
      </button>
    </form>
  );
}
