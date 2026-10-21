import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  ApiRequestError,
  confirmPlace,
  saveDraft,
  searchPlaces,
  stepBack,
  type DraftPayload,
  type PlaceHit,
  type ProfileResponse,
} from "../api/client";
import { Button, Field, LoadingScreen } from "../components/ui/controls";
import { deviceTimezone } from "../deviceZone";
import { useDebouncedValue } from "../placeQuery";
import { formatText, text } from "../resources";
import { readWebApp } from "../telegram";

type OnboardingPageProps = {
  profile: ProfileResponse;
};

type DraftState = {
  name: string;
  birthDate: string;
  birthTime: string;
  unknownTime: boolean;
  zone: string;
  placeQuery: string;
};

export function OnboardingPage({ profile }: OnboardingPageProps) {
  const client = useQueryClient();
  const [name, setName] = useState(profile.display_name ?? "");
  const [birthDate, setBirthDate] = useState(profile.birth_date ?? "");
  const [birthTime, setBirthTime] = useState(profile.birth_time ?? "");
  const [unknownTime, setUnknownTime] = useState(profile.birth_time_unknown);
  const [zone, setZone] = useState(profile.timezone ?? "");
  const [placeQuery, setPlaceQuery] = useState("");
  const stablePlace = useDebouncedValue(placeQuery);
  const [hits, setHits] = useState<PlaceHit[]>([]);
  const [searchedQuery, setSearchedQuery] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const state = { name, birthDate, birthTime, unknownTime, zone, placeQuery };

  useEffect(() => {
    setName(profile.display_name ?? "");
    setBirthDate(profile.birth_date ?? "");
    setBirthTime(profile.birth_time ?? "");
    setUnknownTime(profile.birth_time_unknown);
    setZone(profile.timezone ?? "");
    setFields({});
  }, [profile]);

  const draft = useMutation<ProfileResponse, Error, DraftPayload>({
    mutationFn: (body) => saveDraft(body),
    onSuccess: (next) => {
      client.setQueryData(["session"], next);
      setFields({});
    },
    onError: (error: unknown) => {
      setFields(error instanceof ApiRequestError ? error.fields : {});
    },
  });
  const back = useMutation({
    mutationFn: () => stepBack(),
    onSuccess: (next) => {
      client.setQueryData(["session"], next);
      setFields({});
    },
  });
  const search = useMutation<PlaceHit[], Error, string>({
    mutationFn: (query) => searchPlaces(query),
    onSuccess: (found, query) => {
      setHits(found);
      setSearchedQuery(query);
      setFields({});
    },
    onError: (error: unknown) => {
      setFields(error instanceof ApiRequestError ? error.fields : {});
    },
  });
  const place = useMutation<ProfileResponse, Error, PlaceHit & { query: string }>({
    mutationFn: (body) => confirmPlace(body),
    onSuccess: (next) => {
      client.setQueryData(["session"], next);
      setFields({});
    },
    onError: (error: unknown) => {
      setFields(error instanceof ApiRequestError ? error.fields : {});
    },
  });

  const dirty = isDirty(profile, state);
  const canGoBack = profile.step !== "welcome";
  const pending = draft.isPending || back.isPending || search.isPending || place.isPending;
  const zoneSkip = useRef(false);

  useEffect(() => {
    if (profile.step !== "timezone" || zoneSkip.current) {
      return;
    }
    zoneSkip.current = true;
    void draft.mutateAsync({ timezone: deviceTimezone() });
  }, [draft, profile.step]);
  const failure =
    (draft.isError || search.isError || place.isError) && Object.keys(fields).length === 0;

  useEffect(() => {
    const webApp = readWebApp();
    if (webApp === null) {
      return;
    }
    webApp.setClosingConfirmation(dirty);
    if (!canGoBack) {
      webApp.hideBack();
      return () => {
        webApp.setClosingConfirmation(false);
      };
    }
    const goBack = () => {
      void back.mutateAsync();
    };
    webApp.showBack(goBack);
    return () => {
      webApp.hideBack();
      webApp.setClosingConfirmation(false);
    };
  }, [back.mutateAsync, canGoBack, dirty]);

  if (profile.step === "timezone") {
    if (draft.isError) {
      return (
        <main className="shell">
          <p role="alert">{text("ui.common.error")}</p>
          <Button
            label={text("ui.common.retry")}
            onClick={() => {
              void draft.mutateAsync({ timezone: deviceTimezone() });
            }}
          />
        </main>
      );
    }
    return <LoadingScreen />;
  }

  return (
    <main className="shell">
      <section className="surface">
        <h1>{heading(profile)}</h1>
        {profile.step === "welcome" ? (
          <p className="lead">{text("ui.onboarding.welcome_lead")}</p>
        ) : null}
        {profile.step === "name" ? (
          <Field
            label={text("ui.onboarding.name_title")}
            value={name}
            onChange={setName}
            {...(fields.display_name !== undefined ? { error: fields.display_name } : {})}
          />
        ) : null}
        {profile.step === "date" ? (
          <Field
            label={text("ui.onboarding.date_title")}
            value={birthDate}
            onChange={setBirthDate}
            {...(fields.birth_date !== undefined ? { error: fields.birth_date } : {})}
          />
        ) : null}
        {profile.step === "time" ? (
          <>
            <Field
              label={text("ui.onboarding.time_title")}
              value={birthTime}
              onChange={setBirthTime}
              {...(fields.birth_time !== undefined ? { error: fields.birth_time } : {})}
            />
            <button
              type="button"
              className="choice"
              aria-pressed={unknownTime}
              onClick={() => setUnknownTime((value) => !value)}
            >
              {text("ui.onboarding.time_unknown")}
            </button>
          </>
        ) : null}
        {profile.step === "place" ? (
          <>
            <Field
              label={text("ui.onboarding.place_title")}
              value={placeQuery}
              onChange={setPlaceQuery}
              {...(fields.birth_place !== undefined ? { error: fields.birth_place } : {})}
            />
            <Button
              label={text("ui.common.next")}
              loading={search.isPending}
              disabled={
                pending || stablePlace.trim().length < 2 || stablePlace !== placeQuery
              }
              onClick={() => {
                void search.mutateAsync(stablePlace);
              }}
            />
            <p className="meta">{text("ui.place.attribution")}</p>
            {hits.map((hit) => (
              <button
                key={`${hit.label}:${hit.latitude}:${hit.longitude}`}
                type="button"
                className="choice"
                onClick={() => {
                  void place.mutateAsync({
                    query: searchedQuery,
                    label: hit.label,
                    latitude: hit.latitude,
                    longitude: hit.longitude,
                  });
                }}
              >
                {hit.label}
              </button>
            ))}
          </>
        ) : null}
        {failure ? <p role="alert">{text("ui.common.error")}</p> : null}
        <div className="actions">
          {profile.step !== "place" ? (
            <Button
              label={text("ui.common.next")}
              loading={draft.isPending}
              disabled={pending}
              onClick={() => {
                void draft.mutateAsync(payload(profile.step, state));
              }}
            />
          ) : null}
          {canGoBack ? (
            <Button
              label={text("ui.common.back")}
              disabled={pending}
              onClick={() => {
                void back.mutateAsync();
              }}
            />
          ) : null}
          {dirty ? (
            <Button
              label={text("ui.common.cancel")}
              disabled={pending}
              onClick={() => {
                setName(profile.display_name ?? "");
                setBirthDate(profile.birth_date ?? "");
                setBirthTime(profile.birth_time ?? "");
                setUnknownTime(profile.birth_time_unknown);
                setZone(profile.timezone ?? "");
                setPlaceQuery("");
                setHits([]);
                setFields({});
              }}
            />
          ) : null}
          {failure ? (
            <Button
              label={text("ui.common.retry")}
              disabled={pending}
              onClick={() => {
                if (profile.step === "place") {
                  void search.mutateAsync(stablePlace);
                  return;
                }
                void draft.mutateAsync(payload(profile.step, state));
              }}
            />
          ) : null}
        </div>
      </section>
    </main>
  );
}

function heading(profile: ProfileResponse): string {
  if (profile.step === "welcome") {
    return text("ui.onboarding.welcome_title");
  }
  if (profile.step === "name") {
    return text("ui.onboarding.name_title");
  }
  if (profile.step === "date") {
    return text("ui.onboarding.date_title");
  }
  if (profile.step === "time") {
    return text("ui.onboarding.time_title");
  }
  if (profile.step === "timezone") {
    return text("ui.onboarding.timezone_title");
  }
  if (profile.step === "place") {
    return text("ui.onboarding.place_title");
  }
  if (profile.display_name) {
    return formatText("ui.onboarding.sign_named", { name: profile.display_name });
  }
  return text("ui.onboarding.sign_title");
}

function payload(step: string, state: DraftState) {
  if (step === "name") {
    return { display_name: state.name };
  }
  if (step === "date") {
    return { birth_date: state.birthDate };
  }
  if (step === "time") {
    if (state.unknownTime) {
      return { birth_time_unknown: true, timezone: deviceTimezone() };
    }
    return {
      birth_time: state.birthTime,
      birth_time_unknown: false,
      timezone: deviceTimezone(),
    };
  }
  if (step === "timezone") {
    return { timezone: state.zone };
  }
  return {};
}

function isDirty(profile: ProfileResponse, state: DraftState): boolean {
  if (profile.step === "name") {
    return state.name !== (profile.display_name ?? "");
  }
  if (profile.step === "date") {
    return state.birthDate !== (profile.birth_date ?? "");
  }
  if (profile.step === "time") {
    return (
      state.unknownTime !== profile.birth_time_unknown ||
      state.birthTime !== (profile.birth_time ?? "")
    );
  }
  if (profile.step === "timezone") {
    return state.zone !== (profile.timezone ?? "");
  }
  if (profile.step === "place") {
    return state.placeQuery.trim().length > 0;
  }
  return false;
}
