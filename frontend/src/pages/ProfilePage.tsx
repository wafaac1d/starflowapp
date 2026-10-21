import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  ApiRequestError,
  deleteProfile,
  editProfile,
  openSession,
  type DraftPayload,
  type ProfileResponse,
} from "../api/client";
import { BackHome, Button, Field } from "../components/ui/controls";
import { text } from "../resources";
import { readWebApp } from "../telegram";

type ProfilePageProps = {
  profile: ProfileResponse;
};

export function ProfilePage({ profile }: ProfilePageProps) {
  const client = useQueryClient();
  const [name, setName] = useState(profile.display_name ?? "");
  const [birthDate, setBirthDate] = useState(profile.birth_date ?? "");
  const [birthTime, setBirthTime] = useState(profile.birth_time ?? "");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState(false);
  const dirty =
    name !== (profile.display_name ?? "") ||
    birthDate !== (profile.birth_date ?? "") ||
    birthTime !== (profile.birth_time ?? "");

  useEffect(() => {
    const webApp = readWebApp();
    if (webApp === null) {
      return;
    }
    webApp.setClosingConfirmation(dirty);
    webApp.showBack(() => {
      window.history.back();
    });
    return () => {
      webApp.hideBack();
      webApp.setClosingConfirmation(false);
    };
  }, [dirty]);

  useEffect(() => {
    setName(profile.display_name ?? "");
    setBirthDate(profile.birth_date ?? "");
    setBirthTime(profile.birth_time ?? "");
  }, [profile]);

  const save = useMutation<ProfileResponse, Error, DraftPayload>({
    mutationFn: (body) => editProfile(body),
    onSuccess: (next) => {
      client.setQueryData(["session"], next);
      setFields({});
    },
    onError: (error: unknown) => {
      setFields(error instanceof ApiRequestError ? error.fields : {});
    },
  });
  const remove = useMutation({
    mutationFn: async () => {
      await deleteProfile();
      const webApp = readWebApp();
      if (webApp === null) {
        return null;
      }
      return openSession(webApp.initData);
    },
    onSuccess: (next) => {
      if (next !== null) {
        client.setQueryData(["session"], next);
      }
    },
  });

  if (profile.step !== "done") {
    return (
      <main className="shell">
        <section className="surface">
          <h1>{text("ui.profile.title")}</h1>
          <p className="lead">{text("errors.onboarding_incomplete")}</p>
          <BackHome />
        </section>
      </main>
    );
  }

  return (
    <main className="shell screen-fill">
      <section className="surface">
        <h1>{text("ui.profile.title")}</h1>
        <Field
          label={text("ui.onboarding.name_title")}
          value={name}
          onChange={setName}
          {...(fields.display_name !== undefined ? { error: fields.display_name } : {})}
        />
        <Field
          label={text("ui.onboarding.date_title")}
          value={birthDate}
          onChange={setBirthDate}
          {...(fields.birth_date !== undefined ? { error: fields.birth_date } : {})}
        />
        <Field
          label={text("ui.onboarding.time_title")}
          value={birthTime}
          onChange={setBirthTime}
          {...(fields.birth_time !== undefined ? { error: fields.birth_time } : {})}
        />
        {save.isError && Object.keys(fields).length === 0 ? (
          <p role="alert">{text("ui.common.error")}</p>
        ) : null}
        <div className="actions">
          <Button
            label={text("ui.profile.save")}
            loading={save.isPending}
            onClick={() => {
              void save.mutateAsync(profileEdits(name, birthDate, birthTime));
            }}
          />
          {save.isError && Object.keys(fields).length === 0 ? (
            <Button
              label={text("ui.common.retry")}
              onClick={() => {
                void save.mutateAsync(profileEdits(name, birthDate, birthTime));
              }}
            />
          ) : null}
          <BackHome />
        </div>
      </section>
      <Button
        tone="danger"
        label={confirming ? text("ui.profile.delete_confirm") : text("ui.profile.delete")}
        disabled={remove.isPending}
        onClick={() => {
          if (!confirming) {
            setConfirming(true);
            return;
          }
          void remove.mutateAsync();
        }}
      />
    </main>
  );
}

function profileEdits(name: string, birthDate: string, birthTime: string): DraftPayload {
  const unknown = birthTime.trim().length === 0;
  const body: DraftPayload = {
    display_name: name,
    birth_date: birthDate,
    birth_time_unknown: unknown,
  };
  if (!unknown) {
    body.birth_time = birthTime.trim();
  }
  return body;
}
