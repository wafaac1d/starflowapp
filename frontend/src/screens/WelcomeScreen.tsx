import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { acceptPrivacy } from "../api/client";
import { queryKeys } from "../api/keys";
import { PRIVACY_CHECKED } from "../privacyPolicy";
import { Button } from "../shared/ui/Button/Button";
import { Screen } from "../shared/ui/Screen/Screen";
import styles from "./screens.module.css";

type WelcomeScreenProps = {
  privacyAccepted: boolean;
};

export function WelcomeScreen({ privacyAccepted }: WelcomeScreenProps) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [checked, setChecked] = useState(() => sessionStorage.getItem(PRIVACY_CHECKED) === "1");
  const accept = useMutation({
    mutationFn: acceptPrivacy,
    onSuccess: (next) => {
      client.setQueryData(queryKeys.session, next);
      sessionStorage.removeItem(PRIVACY_CHECKED);
      void navigate("/onboarding/birth");
    },
  });

  function remember(next: boolean) {
    setChecked(next);
    if (next) {
      sessionStorage.setItem(PRIVACY_CHECKED, "1");
    } else {
      sessionStorage.removeItem(PRIVACY_CHECKED);
    }
  }

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
          {privacyAccepted ? null : (
            <label className={styles.consent}>
              <input
                type="checkbox"
                checked={checked}
                onChange={(event) => {
                  remember(event.target.checked);
                }}
              />
              <span className={styles.consentText}>
                Я принимаю{" "}
                <button
                  type="button"
                  className={styles.consentLink}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    void navigate("/privacy");
                  }}
                >
                  соглашение о конфиденциальности
                </button>
              </span>
            </label>
          )}
          {accept.isError ? <p role="alert">Не удалось сохранить согласие</p> : null}
          <Button
            disabled={!privacyAccepted && !checked}
            loading={accept.isPending}
            onClick={() => {
              if (privacyAccepted) {
                void navigate("/onboarding/birth");
                return;
              }
              accept.mutate();
            }}
          >
            Начать
          </Button>
        </div>
      </div>
    </Screen>
  );
}
