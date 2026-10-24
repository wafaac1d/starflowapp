import { Icon } from "../Icon/Icon";
import styles from "./ChatInput.module.css";

type ChatInputProps = {
  value: string;
  pending?: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function ChatInput({ value, pending = false, onChange, onSubmit }: ChatInputProps) {
  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        if (value.trim() === "" || pending) {
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
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
      <button className={styles.send} type="submit" aria-label="отправить" disabled={pending || value.trim() === ""}>
        <Icon name="send" size={36} />
      </button>
    </form>
  );
}
