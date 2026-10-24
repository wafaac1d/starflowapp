import { useNavigate } from "react-router";

import { Button } from "../shared/ui/Button/Button";
import { Screen } from "../shared/ui/Screen/Screen";
import styles from "./screens.module.css";

export function WelcomeScreen() {
  const navigate = useNavigate();
  return (
    <Screen>
      <div className={styles.fill}>
        <img className={styles.hero} src="/illustrations/png/onboarding_eclipse.png" alt="" />
        <h1 className={styles.welcomeTitle}>
          Ваш ритм.
          <br />
          Ваш космос.
        </h1>
        <p className={styles.lead}>
          Астропрогнозы, натальные карты и персональный астропомощник в одном приложении.
        </p>
        <div className={styles.dock}>
          <Button
            onClick={() => {
              void navigate("/onboarding/birth");
            }}
          >
            Начать
          </Button>
        </div>
      </div>
    </Screen>
  );
}
