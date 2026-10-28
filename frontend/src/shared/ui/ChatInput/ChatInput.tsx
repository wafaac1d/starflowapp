import { Icon } from "../Icon/Icon";
import { StarPrice } from "../StarPrice/StarPrice";
import styles from "./ChatInput.module.css";

type ChatInputProps = {
  value: string;
  pending?: boolean;
  locked?: boolean;
  placeholder?: string;
  price?: number;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function ChatInput({
  value,
  pending = false,
  locked = false,
  placeholder = "Написать сообщение…",
  price,
  onChange,
  onSubmit,
}: ChatInputProps) {
  const label = price === undefined ? "Отправить" : `Отправить за ${price}`;
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
        placeholder={placeholder}
        aria-label={placeholder}
        disabled={locked}
        onChange={(event) => {
          if (locked) {
            return;
          }
          onChange(event.target.value);
        }}
      />
      <button
        className={price === undefined ? styles.send : styles.sendPriced}
        type="submit"
        aria-label={label}
        disabled={locked || pending || value.trim() === ""}
      >
        {price !== undefined ? <StarPrice amount={price} /> : null}
        <Icon name="send" size={36} />
      </button>
    </form>
  );
}
