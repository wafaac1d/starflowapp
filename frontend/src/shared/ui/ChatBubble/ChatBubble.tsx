import { Icon } from "../Icon/Icon";
import styles from "./ChatBubble.module.css";

type ChatBubbleProps = {
  role: "user" | "assistant";
  text: string;
  time: string;
};

export function ChatBubble({ role, text, time }: ChatBubbleProps) {
  if (role === "user") {
    return (
      <div className={styles.userWrap}>
        <p className={styles.user}>{text}</p>
        <time className={styles.time}>{time}</time>
      </div>
    );
  }
  return (
    <div className={styles.botWrap}>
      <Icon name="assistant_avatar" size={28} />
      <div>
        <p className={styles.bot}>{text}</p>
        <time className={styles.time}>{time}</time>
      </div>
    </div>
  );
}
