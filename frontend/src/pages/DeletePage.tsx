import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { deleteProfile, openSession } from "../api/client";
import { queryKeys } from "../api/keys";
import { text } from "../resources";
import { Button } from "../shared/ui/Button/Button";
import { Screen } from "../shared/ui/Screen/Screen";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "../screens/screens.module.css";
import { readWebApp } from "../telegram";

type DeletePageProps = {
  fetchImpl?: typeof fetch;
};

export function DeletePage({ fetchImpl }: DeletePageProps) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [confirmed, setConfirmed] = useState(false);
  const remove = useMutation({
    mutationFn: async () => {
      await deleteProfile(fetchImpl);
      const webApp = readWebApp();
      if (webApp === null) {
        return null;
      }
      return openSession(webApp.initData, fetchImpl);
    },
    onSuccess: (next) => {
      if (next !== null) {
        client.setQueryData(queryKeys.session, next);
      }
      void navigate("/");
    },
  });
  return (
    <Screen tab="profile">
      <TopBar title="Удалить данные" back />
      <p className={styles.paragraph}>{text("ui.delete.lead")}</p>
      <p className={styles.paragraph}>{text("ui.delete.kept")}</p>
      <p className={styles.paragraph}>{text("ui.delete.policy")}</p>
      <label className={styles.consent}>
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => {
            setConfirmed(event.target.checked);
          }}
        />
        <span>{text("ui.delete.confirm")}</span>
      </label>
      <div className={styles.dock}>
        <Button
          disabled={!confirmed || remove.isPending}
          onClick={() => {
            void remove.mutateAsync();
          }}
        >
          {text("ui.profile.delete_confirm")}
        </Button>
      </div>
    </Screen>
  );
}
