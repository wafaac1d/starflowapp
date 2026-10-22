import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import {
  ApiRequestError,
  editProfile,
  type DraftPayload,
  type ProfileResponse,
} from "../api/client";
import { maskBirthDate } from "../birthDate";
import { Button, Input } from "../components/ui/controls";
import { EditorialListRow, PageHeader, ProfileSummary } from "../components/ui/editorial";
import { text, type TextKey } from "../resources";
import { readWebApp } from "../telegram";

type ProfilePageProps = {
  profile: ProfileResponse;
};

const MORE: { to: string; label: TextKey }[] = [
  { to: "/reading/today_detail", label: "ui.reading.today_detail" },
  { to: "/reading/tomorrow", label: "ui.reading.tomorrow" },
  { to: "/reading/personal_day", label: "ui.reading.personal_day" },
  { to: "/reading/personal_week", label: "ui.reading.personal_week" },
  { to: "/reading/personal_month", label: "ui.reading.personal_month" },
  { to: "/reading/topics?topic=отношения", label: "ui.reading.topics" },
  { to: "/assistant", label: "ui.assistant.title" },
  { to: "/reading/week", label: "ui.reading.week" },
  { to: "/reading/compatibility", label: "ui.reading.compatibility" },
  { to: "/referral", label: "ui.reading.referral" },
  { to: "/retro", label: "ui.retro.title" },
  { to: "/premium", label: "ui.premium.title" },
];

export function ProfilePage({ profile }: ProfilePageProps) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const editing = params.get("edit") === "birth";
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
      void navigate("/profile", { replace: true });
    },
    onError: (error: unknown) => {
      setFields(error instanceof ApiRequestError ? error.fields : {});
    },
  });

  if (profile.step !== "done") {
    return (
      <main className="shell page">
        <PageHeader title={text("ui.profile.title")} />
        <p className="lead">{text("errors.onboarding_incomplete")}</p>
      </main>
    );
  }

  if (editing) {
    return (
      <main className="shell page">
        <PageHeader title={text("ui.profile.birth_row")} backTo="/profile" />
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
        </div>
      </main>
    );
  }

  return (
    <main className="shell page">
      <h1 className="page-title">{text("ui.profile.title")}</h1>
      <ProfileSummary
        name={profile.display_name ?? text("ui.profile.unnamed")}
        sign={profile.calendar_sign}
        premium={profile.is_premium}
      />
      <div className="editorial-list">
        <EditorialListRow
          index="01"
          label={text("ui.profile.birth_row")}
          hint={birthLine(profile)}
          arrow
          onClick={() => {
            void navigate("/profile?edit=birth");
          }}
        />
        <EditorialListRow
          index="02"
          label={text("ui.chart.title")}
          arrow
          onClick={() => {
            void navigate("/chart");
          }}
        />
        <EditorialListRow
          index="03"
          label={text("ui.reading.favorites")}
          arrow
          onClick={() => {
            void navigate("/favorites");
          }}
        />
        <EditorialListRow
          index="04"
          label={text("ui.reading.history")}
          arrow
          onClick={() => {
            void navigate("/history");
          }}
        />
        <EditorialListRow
          index="05"
          label={text("ui.settings.title")}
          arrow
          onClick={() => {
            void navigate("/settings");
          }}
        />
        {MORE.map((item) => (
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
      {profile.is_admin ? (
        <Button
          tone="outline"
          label={text("ui.admin.title")}
          onClick={() => {
            void navigate("/admin");
          }}
        />
      ) : null}
    </main>
  );
}

function birthLine(profile: ProfileResponse): string {
  const date = profile.birth_date ?? text("ui.profile.date_missing");
  const unknown =
    profile.birth_time_unknown || profile.birth_time === null || profile.birth_time.trim() === "";
  const time = unknown ? text("ui.profile.time_missing") : profile.birth_time;
  return `${date} · ${time}`;
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
