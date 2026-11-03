import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { getNotifications, saveNotifications, type NoticePrefs } from "../api/client";
import { queryKeys } from "../api/keys";
import { ListRow } from "../shared/ui/ListRow/ListRow";
import { Screen } from "../shared/ui/Screen/Screen";
import { Toggle } from "../shared/ui/Toggle/Toggle";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

export function SettingsScreen() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [master, setMaster] = useState(true);
  const [reminders, setReminders] = useState(true);
  const notices = useQuery({ queryKey: queryKeys.notifications, queryFn: () => getNotifications() });
  const save = useMutation({
    mutationFn: (next: NoticePrefs) => saveNotifications(next),
    onSuccess: (saved) => {
      client.setQueryData(queryKeys.notifications, saved);
    },
  });
  const current = notices.data;
  const patch = (part: Partial<NoticePrefs>) => {
    if (current === undefined) {
      return;
    }
    save.mutate({ ...current, ...part });
  };
  return (
    <Screen tab="profile">
      <TopBar title="Настройки" back />
      <div className={styles.settings}>
      <div className={styles.group}>
        <Toggle label="Уведомления" checked={master} onChange={setMaster} />
        <Toggle
          label="Ежедневный прогноз"
          checked={current?.day ?? true}
          onChange={(checked) => {
            patch({ day: checked });
          }}
        />
        <Toggle label="Напоминания" checked={reminders} onChange={setReminders} />
      </div>
        <ListRow
          icon="settings_time"
          title="Время"
          value={current?.local_time ?? "08:30"}
          onClick={() => {
            patch({ local_time: current?.local_time === "08:30" ? "09:00" : "08:30" });
          }}
        />
        <ListRow icon="settings_timezone" title="Часовой пояс" value={zoneLabel(current?.timezone)} />
        <ListRow
          icon="settings_help"
          title="Помощь"
          chevron
          onClick={() => {
            void navigate("/help");
          }}
        />
      </div>
    </Screen>
  );
}

function zoneLabel(timezone: string | null | undefined): string {
  if (timezone === "Europe/Moscow" || timezone === undefined || timezone === null) {
    return "UTC+3";
  }
  return timezone;
}
