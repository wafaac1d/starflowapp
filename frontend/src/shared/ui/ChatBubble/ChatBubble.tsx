import { Icon } from "../Icon/Icon";
import styles from "./ChatBubble.module.css";

type ChatBubbleProps = {
  role: "user" | "assistant";
  text: string;
  time: string;
  pending?: boolean;
  announce?: boolean;
};

export function ChatBubble({ role, text, time, pending = false, announce = false }: ChatBubbleProps) {
  if (role === "user") {
    return (
      <div className={styles.userWrap}>
        <p className={styles.user}>{text}</p>
        {time !== "" ? <time className={styles.time}>{time}</time> : null}
      </div>
    );
  }
  return (
    <div className={styles.botWrap}>
      <Icon name="assistant_avatar" size={28} />
      <div>
        <p
          className={styles.bot}
          {...(announce ? { role: "status" as const, "aria-live": "polite" as const } : {})}
          {...(pending ? { "aria-label": "Астропомощник отвечает" } : {})}
        >
          {pending ? (
            <span className={styles.dots} aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          ) : (
            text
          )}
        </p>
        {time !== "" ? <time className={styles.time}>{time}</time> : null}
      </div>
    </div>
  );
}
