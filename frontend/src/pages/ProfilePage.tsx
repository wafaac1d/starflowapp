import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router";

import {
  ApiRequestError,
  deleteProfile,
  editProfile,
  openSession,
  type DraftPayload,
  type ProfileResponse,
} from "../api/client";
import { Button, Field } from "../components/ui/controls";
import { text } from "../resources";
import { readWebApp } from "../telegram";

type ProfilePageProps = {
  profile: ProfileResponse;
};

export function ProfilePage({ profile }: ProfilePageProps) {
  const client = useQueryClient();
  const [name, setName] = useState(profile.display_name ?? "");
  const [birthDate, setBirthDate] = useState(profile.birth_date ?? "");
  const [zone, setZone] = useState(profile.timezone ?? "");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState(false);
  const dirty =
    name !== (profile.display_name ?? "") ||
    birthDate !== (profile.birth_date ?? "") ||
    zone !== (profile.timezone ?? "");

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
          <Link to="/">{text("ui.common.back")}</Link>
        </section>
      </main>
    );
  }

  return (
    <main className="shell">
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
          label={text("ui.onboarding.timezone_title")}
          value={zone}
          onChange={setZone}
          {...(fields.timezone !== undefined ? { error: fields.timezone } : {})}
        />
        {save.isError && Object.keys(fields).length === 0 ? (
          <p role="alert">{text("ui.common.error")}</p>
        ) : null}
        <div className="actions">
          <Button
            label={text("ui.profile.save")}
            loading={save.isPending}
            onClick={() => {
              void save.mutateAsync({ display_name: name, birth_date: birthDate, timezone: zone });
            }}
          />
          {save.isError && Object.keys(fields).length === 0 ? (
            <Button
              label={text("ui.common.retry")}
              onClick={() => {
                void save.mutateAsync({
                  display_name: name,
                  birth_date: birthDate,
                  timezone: zone,
                });
              }}
            />
          ) : null}
          <Button
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
          <Link to="/">{text("ui.common.back")}</Link>
        </div>
      </section>
    </main>
  );
}
