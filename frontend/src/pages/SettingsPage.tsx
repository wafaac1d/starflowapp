import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import {
  NOTICE_SLOTS,
  getNotifications,
  saveNotifications,
  type NoticePrefs,
} from "../api/client";
import { Button, ErrorState, Skeleton } from "../components/ui/controls";
import {
  EditorialListRow,
  PageHeader,
  Switch,
  ThemeSelector,
} from "../components/ui/editorial";
import { Icon } from "../components/ui/icons";
import { text } from "../resources";
import { applyTheme, readThemeChoice, type ThemeChoice } from "../theme";

type SettingsPageProps = {
  fetchImpl?: typeof fetch;
};

export function SettingsPage({ fetchImpl = fetch }: SettingsPageProps) {
  const navigate = useNavigate();
  const client = useQueryClient();
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
    <main className="shell page">
      <PageHeader title={text("ui.settings.title")} backTo="/profile" />
      <h2>{text("ui.settings.appearance")}</h2>
      <ThemeSelector
        value={choice}
        onChange={(next) => {
          applyTheme(next);
          setChoice(next);
        }}
      />
      <h2>{text("ui.settings.notices")}</h2>
      <p className="lead">{text("ui.settings.lead")}</p>
      {notice.isPending ? <Skeleton /> : null}
      {notice.isError ? (
        <ErrorState
          message={text("ui.common.error")}
          onRetry={() => {
            void notice.refetch();
          }}
        />
      ) : null}
      {draft === null ? null : (
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            void save.mutateAsync(draft);
          }}
        >
          <label className="setting-row">
            <span>{text("ui.settings.time")}</span>
            <span className="setting-control">
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
              <Icon name="arrow-right" />
            </span>
          </label>
          <label className="setting-row">
            <span>{text("ui.settings.timezone")}</span>
            <span className="setting-control">
              <input
                className="as-typed"
                value={draft.timezone}
                onChange={(event) => {
                  setDraft({ ...draft, timezone: event.target.value });
                }}
                aria-label={text("ui.settings.timezone")}
              />
              <Icon name="arrow-right" />
            </span>
          </label>
          <Switch
            label={text("ui.settings.day")}
            checked={draft.day}
            onChange={(day) => {
              setDraft({ ...draft, day });
            }}
          />
          <Switch
            label={text("ui.settings.moon")}
            checked={draft.moon}
            onChange={(moon) => {
              setDraft({ ...draft, moon });
            }}
          />
          <Switch
            label={text("ui.settings.retro")}
            checked={draft.retro}
            onChange={(retro) => {
              setDraft({ ...draft, retro });
            }}
          />
          {save.isError ? <p role="alert">{text("ui.common.error")}</p> : null}
          <Button
            label={text("ui.settings.save")}
            loading={save.isPending}
            onClick={() => {
              void save.mutateAsync(draft);
            }}
          />
        </form>
      )}
      <div className="editorial-list">
        <EditorialListRow
          label={text("ui.help.title")}
          arrow
          onClick={() => {
            void navigate("/help");
          }}
        />
        <EditorialListRow
          label={text("ui.terms.title")}
          arrow
          onClick={() => {
            void navigate("/terms");
          }}
        />
        <EditorialListRow
          label={text("ui.paysupport.title")}
          arrow
          onClick={() => {
            void navigate("/paysupport");
          }}
        />
        <EditorialListRow
          label={text("ui.settings.account")}
          arrow
          onClick={() => {
            void navigate("/delete");
          }}
        />
      </div>
    </main>
  );
}
