import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import {
  confirmPlace,
  editProfile,
  saveDraft,
  searchPlaces,
  type DraftPayload,
  type PlaceHit,
  type ProfileResponse,
} from "../api/client";
import { maskBirthDate, maskBirthTime } from "../birthDate";
import { queryKeys } from "../api/keys";
import { deviceTimezone } from "../deviceZone";
import { useDebouncedValue } from "../placeQuery";
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

export function formatPlaceLabel(label: string): string {
  const parts = label
    .split(",")
    .map((p) => p.trim())
    .filter((p): p is string => Boolean(p));
  if (parts.length <= 1) {
    return label.trim();
  }
  const city = parts[0] ?? "";
  if (parts.length === 2) {
    return `${parts[0]}, ${parts[1]}`;
  }
  let country = parts[parts.length - 1] ?? "";
  if (/^\d+$/.test(country) && parts.length >= 3) {
    country = parts[parts.length - 2] ?? "";
  }
  if (!country || country.toLowerCase() === city.toLowerCase()) {
    return city;
  }
  return `${country}, ${city}`;
}

export function BirthScreen({ profile, displayName }: BirthScreenProps) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [date, setDate] = useState(profile.birth_date ?? "");
  const [time, setTime] = useState(profile.birth_time ?? "");
  const [placeQuery, setPlaceQuery] = useState(
    profile.birth_place ? formatPlaceLabel(profile.birth_place) : ""
  );
  const [selectedPlace, setSelectedPlace] = useState<PlaceHit | null>(null);
  const [hits, setHits] = useState<PlaceHit[]>([]);
  const stablePlace = useDebouncedValue(placeQuery);

  useEffect(() => {
    const q = stablePlace.trim();
    if (q.length < 2 || selectedPlace !== null || q === (profile.birth_place ?? "").trim()) {
      setHits([]);
      return;
    }
    let active = true;
    void searchPlaces(q)
      .then((found) => {
        if (active) {
          setHits(found);
        }
      })
      .catch(() => {
        if (active) {
          setHits([]);
        }
      });
    return () => {
      active = false;
    };
  }, [stablePlace, selectedPlace, profile.birth_place]);

  const save = useMutation({
    mutationFn: async () => {
      const clock = timeDraft(time);
      let placeToConfirm: PlaceHit | null | undefined = selectedPlace;
      if (
        !placeToConfirm &&
        placeQuery.trim().length >= 2 &&
        placeQuery.trim() !== (profile.birth_place ?? "").trim()
      ) {
        try {
          const found = await searchPlaces(placeQuery.trim());
          if (found.length > 0 && found[0]) {
            placeToConfirm = found[0];
          }
        } catch {
          // ignore geocode search failure
        }
      }

      if (profile.step === "done") {
        const clearPlace = placeQuery.trim() === "" && !!profile.birth_place;
        let current = await editProfile({
          birth_date: date,
          ...clock,
          ...(clearPlace ? { clear_place: true } : {}),
        });
        if (placeToConfirm) {
          current = await confirmPlace({
            query: placeQuery,
            label: placeToConfirm.label,
            latitude: placeToConfirm.latitude,
            longitude: placeToConfirm.longitude,
          });
        }
        return current;
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

      if (placeToConfirm) {
        current = await confirmPlace({
          query: placeQuery,
          label: placeToConfirm.label,
          latitude: placeToConfirm.latitude,
          longitude: placeToConfirm.longitude,
        });
      }

      return current;
    },
    onSuccess: (next) => {
      client.setQueryData(queryKeys.session, next);
      void client.invalidateQueries({ queryKey: queryKeys.chart });
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
        <p className={styles.lead}>Укажите дату, время и город рождения, чтобы получить точный прогноз.</p>
        <div className={styles.stack}>
          <Field
            label="Дата рождения"
            icon="date_calendar"
            value={date}
            onChange={(value) => {
              setDate(maskBirthDate(value));
            }}
          />
          <div className={styles.fieldNote}>
            <Field
              label="Время рождения"
              icon="clock"
              value={time}
              onChange={(value) => {
                setTime(maskBirthTime(value));
              }}
            />
            <p className={styles.meta}>Можно оставить пустым, если не знаете время рождения</p>
          </div>
          <div className={styles.fieldNote}>
            <Field
              label="Город рождения"
              value={placeQuery}
              chevron={false}
              onChange={(value) => {
                setPlaceQuery(value);
                setSelectedPlace(null);
              }}
            />
            <p className={styles.meta}>Можно оставить пустым, если не хотите указывать город</p>
            {hits.length > 0 ? (
              <div className={styles.placeMenu} role="listbox" aria-label="Города">
                {hits.map((hit) => {
                  const label = formatPlaceLabel(hit.label);
                  return (
                    <button
                      key={`${hit.label}:${hit.latitude}`}
                      type="button"
                      className={styles.placeItem}
                      onClick={() => {
                        setPlaceQuery(label);
                        setSelectedPlace({ ...hit, label });
                        setHits([]);
                      }}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            ) : null}
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
