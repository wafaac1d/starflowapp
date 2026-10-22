import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import {
  ApiRequestError,
  editProfile,
  type DraftPayload,
  type ProfileResponse,
} from "../api/client";
import { maskBirthDate } from "../birthDate";
import { BackHome, Button, Input } from "../components/ui/controls";
import { EditorialListRow } from "../components/ui/editorial";
import { text, type TextKey } from "../resources";
import { readWebApp } from "../telegram";

type ProfilePageProps = {
  profile: ProfileResponse;
};

const HUB: { to: string; label: TextKey }[] = [
  { to: "/chart", label: "ui.chart.title" },
  { to: "/reading/today_detail", label: "ui.reading.today_detail" },
  { to: "/reading/tomorrow", label: "ui.reading.tomorrow" },
  { to: "/reading/personal_day", label: "ui.reading.personal_day" },
  { to: "/reading/personal_week", label: "ui.reading.personal_week" },
  { to: "/reading/personal_month", label: "ui.reading.personal_month" },
  { to: "/reading/topics?topic=отношения", label: "ui.reading.topics" },
  { to: "/assistant", label: "ui.assistant.title" },
  { to: "/reading/week", label: "ui.reading.week" },
  { to: "/reading/compatibility", label: "ui.reading.compatibility" },
  { to: "/history", label: "ui.reading.history" },
  { to: "/favorites", label: "ui.reading.favorites" },
  { to: "/referral", label: "ui.reading.referral" },
  { to: "/settings", label: "ui.settings.title" },
  { to: "/retro", label: "ui.retro.title" },
  { to: "/premium", label: "ui.premium.title" },
  { to: "/help", label: "ui.help.title" },
  { to: "/terms", label: "ui.terms.title" },
  { to: "/paysupport", label: "ui.paysupport.title" },
];

export function ProfilePage({ profile }: ProfilePageProps) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [name, setName] = useState(profile.display_name ?? "");
  const [birthDate, setBirthDate] = useState(profile.birth_date ?? "");
  const [birthTime, setBirthTime] = useState(profile.birth_time ?? "");
  const [fields, setFields] = useState<Record<string, string>>({});
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

  if (profile.step !== "done") {
    return (
      <main className="shell">
        <h1>{text("ui.profile.title")}</h1>
        <p className="lead">{text("errors.onboarding_incomplete")}</p>
        <BackHome />
      </main>
    );
  }

  return (
    <main className="shell screen-fill">
      <section>
        <h1>{text("ui.profile.title")}</h1>
        <Input
          label={text("ui.onboarding.name_title")}
          value={name}
          onChange={setName}
          {...(fields.display_name !== undefined ? { error: fields.display_name } : {})}
        />
        <Input
          label={text("ui.onboarding.date_title")}
          value={birthDate}
          inputMode="numeric"
          onChange={(value) => {
            setBirthDate(maskBirthDate(value));
          }}
          {...(fields.birth_date !== undefined ? { error: fields.birth_date } : {})}
        />
        <Input
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
        <div className="editorial-list">
          {HUB.map((item) => (
            <EditorialListRow
              key={item.to}
              label={text(item.label)}
              arrow
              onClick={() => {
                void navigate(item.to);
              }}
            />
          ))}
        </div>
      </section>
      {profile.is_admin ? (
        <Button
          tone="outline"
          label={text("ui.admin.title")}
          onClick={() => {
            void navigate("/admin");
          }}
        />
      ) : null}
      <Button
        tone="danger"
        label={text("ui.profile.delete")}
        onClick={() => {
          void navigate("/delete");
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
