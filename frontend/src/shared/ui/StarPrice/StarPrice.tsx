import { Icon } from "../Icon/Icon";
import styles from "./StarPrice.module.css";

type StarPriceProps = {
  amount: number;
};

export function StarPrice({ amount }: StarPriceProps) {
  return (
    <span className={styles.price}>
      <Icon name="stars_currency" size={16} />
      {amount}
    </span>
  );
}
