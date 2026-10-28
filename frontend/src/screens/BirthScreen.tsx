import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { editProfile, saveDraft, type DraftPayload, type ProfileResponse } from "../api/client";
import { queryKeys } from "../api/keys";
import { deviceTimezone } from "../deviceZone";
import { Button } from "../shared/ui/Button/Button";
import { ErrorState } from "../shared/ui/ErrorState/ErrorState";
import { Field } from "../shared/ui/Field/Field";
import { Screen } from "../shared/ui/Screen/Screen";
import { Stepper } from "../shared/ui/Stepper/Stepper";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

type BirthScreenProps = {
  profile: ProfileResponse;
  displayName: string;
};

function timeDraft(value: string): DraftPayload {
  const clock = value.trim();
  if (clock.length === 0) {
    return { birth_time_unknown: true };
  }
  return { birth_time_unknown: false, birth_time: clock };
}

export function BirthScreen({ profile, displayName }: BirthScreenProps) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [date, setDate] = useState(profile.birth_date ?? "");
  const [time, setTime] = useState(profile.birth_time ?? "");
  const save = useMutation({
    mutationFn: async () => {
      const clock = timeDraft(time);
      if (profile.step === "done") {
        return editProfile({ birth_date: date, ...clock });
      }
      let current = profile;
      const name = current.display_name ?? displayName;
      for (let hop = 0; hop < 6; hop += 1) {
        const step = current.step;
        if (step === "welcome" || step === "name") {
          current = await saveDraft({ display_name: name });
        } else if (step === "date") {
          current = await saveDraft({ birth_date: date });
        } else if (step === "time") {
          current = await saveDraft({ ...clock, timezone: deviceTimezone() });
        } else if (step === "timezone") {
          current = await saveDraft({ timezone: current.timezone ?? deviceTimezone() });
        } else {
          break;
        }
        if (current.step === step) {
          break;
        }
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
          <div className={styles.fieldNote}>
            <Field label="Время рождения" icon="clock" value={time} onChange={setTime} />
            <p className={styles.meta}>Можно оставить пустым, если не знаете время рождения</p>
          </div>
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
