import { Button } from "../Button/Button";
import styles from "./ErrorState.module.css";

type ErrorStateProps = {
  message: string;
  onRetry?: () => void;
};

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className={styles.box}>
      <p role="alert">{message}</p>
      {onRetry !== undefined ? (
        <Button variant="secondary" onClick={onRetry}>
          Повторить
        </Button>
      ) : null}
    </div>
  );
}
