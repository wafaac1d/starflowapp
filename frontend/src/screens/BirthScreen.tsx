import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { saveDraft, type ProfileResponse } from "../api/client";
import { queryKeys } from "../api/keys";
import { deviceTimezone } from "../deviceZone";
import { Button } from "../shared/ui/Button/Button";
import { ErrorState } from "../shared/ui/ErrorState/ErrorState";
import { Field } from "../shared/ui/Field/Field";
import { Screen } from "../shared/ui/Screen/Screen";
import { Stepper } from "../shared/ui/Stepper/Stepper";
import { Toggle } from "../shared/ui/Toggle/Toggle";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

type BirthScreenProps = {
  profile: ProfileResponse;
  displayName: string;
};

export function BirthScreen({ profile, displayName }: BirthScreenProps) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [date, setDate] = useState(profile.birth_date ?? "");
  const [time, setTime] = useState(profile.birth_time ?? "");
  const [unknown, setUnknown] = useState(profile.birth_time_unknown);
  const save = useMutation({
    mutationFn: async () => {
      let current = profile;
      if (current.step === "welcome" || current.step === "name") {
        const name = current.display_name ?? displayName;
        current = await saveDraft({ display_name: name });
      }
      if (current.step === "date" || current.step === "welcome" || current.step === "name") {
        current = await saveDraft({ birth_date: date });
      }
      if (current.step === "time") {
        current = await saveDraft({
          birth_time_unknown: unknown,
          ...(unknown ? {} : { birth_time: time }),
        });
      }
      if (current.step === "timezone") {
        current = await saveDraft({ timezone: current.timezone ?? deviceTimezone() });
      }
      return current;
    },
    onSuccess: (next) => {
      client.setQueryData(queryKeys.session, next);
      if (next.step === "done") {
        void navigate("/");
      }
    },
  });
  return (
    <Screen>
      <div className={styles.fill}>
        <TopBar back />
        <Stepper label="1 из 3" />
        <h1 className={styles.welcomeTitle}>Когда вы родились?</h1>
        <p className={styles.lead}>Укажите дату и время рождения, чтобы получить точный прогноз.</p>
        <div className={styles.stack}>
          <Field label="Дата рождения" icon="date_calendar" value={date} onChange={setDate} />
          <Field
            label="Время рождения"
            icon="clock"
            value={unknown ? "" : time}
            disabled={unknown}
            onChange={setTime}
          />
          <Toggle label="Не знаю время" checked={unknown} onChange={setUnknown} />
        </div>
        {save.isError ? <ErrorState message="Не удалось сохранить данные рождения" /> : null}
        <div className={styles.dock}>
          <Button
            loading={save.isPending}
            onClick={() => {
              save.mutate();
            }}
          >
            Продолжить
          </Button>
        </div>
      </div>
    </Screen>
  );
}
