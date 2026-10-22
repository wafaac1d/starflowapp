import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  NOTICE_SLOTS,
  getNotifications,
  saveNotifications,
  type NoticePrefs,
} from "../api/client";
import { BackHome, BottomSheet, Button } from "../components/ui/controls";
import { text, type TextKey } from "../resources";
import { applyTheme, readThemeChoice, type ThemeChoice } from "../theme";

const THEMES: { id: ThemeChoice; label: TextKey }[] = [
  { id: "light", label: "ui.theme.light" },
  { id: "dark", label: "ui.theme.dark" },
  { id: "telegram", label: "ui.theme.telegram" },
];

type SettingsPageProps = {
  fetchImpl?: typeof fetch;
};

export function SettingsPage({ fetchImpl = fetch }: SettingsPageProps) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [choice, setChoice] = useState<ThemeChoice>(readThemeChoice());
  const notice = useQuery({
    queryKey: ["notifications"],
    queryFn: () => getNotifications(fetchImpl),
  });
  const [draft, setDraft] = useState<NoticePrefs | null>(null);
  useEffect(() => {
    if (notice.data !== undefined) {
      setDraft(notice.data);
    }
  }, [notice.data]);
  const save = useMutation({
    mutationFn: (body: NoticePrefs) => saveNotifications(body, fetchImpl),
    onSuccess: (next) => {
      setDraft(next);
      client.setQueryData(["notifications"], next);
    },
  });
  return (
    <main className="shell">
      <h1>{text("ui.settings.title")}</h1>
      <p className="lead">{text("ui.settings.lead")}</p>
      <p>{text(THEMES.find((item) => item.id === choice)?.label ?? "ui.theme.light")}</p>
      <Button
        tone="outline"
        label={text("ui.theme.open")}
        onClick={() => {
          setOpen(true);
        }}
      />
      {draft === null ? null : (
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            void save.mutateAsync(draft);
          }}
        >
          <label className="field">
            <span>{text("ui.settings.time")}</span>
            <select
              value={draft.local_time}
              onChange={(event) => {
                setDraft({ ...draft, local_time: event.target.value });
              }}
            >
              {NOTICE_SLOTS.map((slot) => (
                <option key={slot} value={slot}>
                  {slot}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{text("ui.settings.timezone")}</span>
            <input
              className="as-typed"
              value={draft.timezone}
              onChange={(event) => {
                setDraft({ ...draft, timezone: event.target.value });
              }}
              aria-label={text("ui.settings.timezone")}
            />
          </label>
          <NoticeToggle
            label={text("ui.settings.day")}
            checked={draft.day}
            onChange={(day) => {
              setDraft({ ...draft, day });
            }}
          />
          <NoticeToggle
            label={text("ui.settings.moon")}
            checked={draft.moon}
            onChange={(moon) => {
              setDraft({ ...draft, moon });
            }}
          />
          <NoticeToggle
            label={text("ui.settings.retro")}
            checked={draft.retro}
            onChange={(retro) => {
              setDraft({ ...draft, retro });
            }}
          />
          <Button
            label={text("ui.settings.save")}
            onClick={() => {
              void save.mutateAsync(draft);
            }}
          />
        </form>
      )}
      <BottomSheet
        open={open}
        title={text("ui.theme.title")}
        onClose={() => {
          setOpen(false);
        }}
      >
        <div className="stack">
          {THEMES.map((item) => (
            <Button
              key={item.id}
              {...(item.id === choice ? {} : { tone: "outline" as const })}
              label={text(item.label)}
              onClick={() => {
                applyTheme(item.id);
                setChoice(item.id);
                setOpen(false);
              }}
            />
          ))}
        </div>
      </BottomSheet>
      <BackHome />
    </main>
  );
}

function NoticeToggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="consent-row">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => {
          onChange(event.target.checked);
        }}
      />
      <span>{label}</span>
    </label>
  );
}
