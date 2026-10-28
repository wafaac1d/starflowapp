import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router";

import {
  addRelated,
  ApiRequestError,
  getRelated,
  readingKey,
  spendStars,
  type ProfileResponse,
  type RelatedEntry,
} from "../api/client";
import { compatRows, getCompatRows, partnerFixture, peopleFixture } from "../api/fixtures";
import { queryKeys } from "../api/keys";
import { maskBirthDate } from "../birthDate";
import { calendarSign, displayBirthDate } from "../calendarSign";
import { titled } from "../case";
import { Avatar } from "../shared/ui/Avatar/Avatar";
import { Button } from "../shared/ui/Button/Button";
import { ErrorState } from "../shared/ui/ErrorState/ErrorState";
import { Field } from "../shared/ui/Field/Field";
import { ListRow } from "../shared/ui/ListRow/ListRow";
import { Screen } from "../shared/ui/Screen/Screen";
import { StarPrice } from "../shared/ui/StarPrice/StarPrice";
import { holdStarBalance, writeStarBalance } from "../starBalance";
import { COMPATIBILITY_STARS } from "../stars";
import { SegmentedControl } from "../shared/ui/SegmentedControl/SegmentedControl";
import { Toggle } from "../shared/ui/Toggle/Toggle";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import { initialsOf } from "./format";
import styles from "./screens.module.css";
import { TopUpDialog } from "./TopUpDialog";
import { useTopicDetail } from "./topicDetail";

type Choice = "self" | "saved" | "draft";

type SlotState = {
  choice: Choice;
  savedId: string;
  name: string;
  date: string;
  time: string;
  save: boolean;
};

type KnownPerson = {
  id: string;
  name: string;
  birthDate: string;
  birthTime: string;
};

type ResolvedPerson = {
  initials: string;
  name: string;
  birthDate: string;
  sign: string;
};

const LINK_MS = 2000;

type Phase = "pick" | "link" | "result";

const EMPTY_SLOT: SlotState = {
  choice: "draft",
  savedId: "",
  name: "",
  date: "",
  time: "",
  save: false,
};

export function CompatibilityScreen({ profile }: { profile: ProfileResponse }) {
  const params = useParams();
  const personId = params.personId;
  const [left, setLeft] = useState<SlotState>({ ...EMPTY_SLOT, choice: "self" });
  const [right, setRight] = useState<SlotState>(() =>
    personId !== undefined && personId !== ""
      ? { ...EMPTY_SLOT, choice: "saved", savedId: personId }
      : { ...EMPTY_SLOT, choice: "draft" },
  );
  const [remembered, setRemembered] = useState<KnownPerson[]>([]);
  const [phase, setPhase] = useState<Phase>("pick");
  const [topUp, setTopUp] = useState(false);
  const [notice, setNotice] = useState("");
  const queryClient = useQueryClient();
  const related = useQuery({ queryKey: queryKeys.related, queryFn: () => getRelated() });
  const rows = useQuery({
    queryKey: queryKeys.compatibility(personId ?? "pair"),
    queryFn: getCompatRows,
  });
  const people = knownPeople(related.data, remembered, personId);
  const owner = resolveSlot(left, profile, people);
  const partner = resolveSlot(right, profile, people);
  const topics = useTopicDetail(profile.is_premium, {
    leftSign: owner?.sign.toLocaleLowerCase("ru") ?? "",
    rightSign: partner?.sign.toLocaleLowerCase("ru") ?? "",
  });
  const remember = (person: KnownPerson) => {
    setRemembered((current) =>
      current.some((item) => item.id === person.id) ? current : [...current, person],
    );
  };
  useEffect(() => {
    if (phase !== "link") {
      return;
    }
    if (reducedMotion()) {
      setPhase("result");
      return;
    }
    const timer = window.setTimeout(() => {
      setPhase("result");
    }, LINK_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [phase]);
  const ready = owner !== null && partner !== null;
  return (
    <Screen tab="today">
      <TopBar
        title="Совместимость"
        back
        {...(phase === "pick" ? {} : { onBack: () => setPhase("pick") })}
      />
      {phase === "pick" ? (
        <div className={styles.fill}>
          <div className={styles.stack}>
            <PersonSlot
              headingId="compat-first"
              legend="Первый человек"
              slot={left}
              people={people}
              profile={profile}
              onChange={setLeft}
              onRemember={remember}
            />
            <PersonSlot
              headingId="compat-second"
              legend="Второй человек"
              slot={right}
              people={people}
              profile={profile}
              onChange={setRight}
              onRemember={remember}
            />
          </div>
          <div className={styles.todayAction}>
            <Button
              disabled={!ready}
              onClick={() => {
                if (!ready || owner === null || partner === null) {
                  return;
                }
                setNotice("");
                if (profile.is_premium) {
                  setPhase("link");
                  return;
                }
                setPhase("link");
                const restore = holdStarBalance(queryClient, COMPATIBILITY_STARS);
                void spendStars({
                  feature: "compatibility",
                  left_sign: owner.sign.toLocaleLowerCase("ru"),
                  right_sign: partner.sign.toLocaleLowerCase("ru"),
                })
                  .then((ticket) => {
                    if (ticket.charged) {
                      writeStarBalance(queryClient, ticket.balance);
                    } else {
                      restore();
                    }
                    if (!ticket.allowed) {
                      setPhase("pick");
                      setTopUp(true);
                    }
                  })
                  .catch((error: unknown) => {
                    restore();
                    setPhase("pick");
                    if (error instanceof ApiRequestError && error.status === 402) {
                      setTopUp(true);
                      return;
                    }
                    setNotice("Не удалось списать звёзды.");
                  });
              }}
            >
              Проверить
              {profile.is_premium ? null : <StarPrice amount={COMPATIBILITY_STARS} />}
            </Button>
            {notice !== "" ? <p role="alert">{notice}</p> : null}
          </div>
        </div>
      ) : null}
      {phase === "link" ? (
        <div className={styles.linkStage} role="status">
          <img className={styles.linkWheel} src="/illustrations/png/compatibility_diagram.png" alt="" />
          <p>Связь со звёздами</p>
        </div>
      ) : null}
      {phase === "result" && owner !== null && partner !== null ? (
        <>
          <div className={styles.pair}>
            <PersonCard person={owner} />
            <PersonCard person={partner} />
          </div>
          <img
            className={styles.compatWheel}
            src="/illustrations/png/compatibility_diagram.png"
            alt=""
          />
          <div className={styles.stack}>
            {(rows.data ?? compatRows).map((row) => (
              <ListRow
                key={row.id}
                icon={row.icon}
                title={row.title}
                subtitle={row.subtitle}
                onClick={() => {
                  topics.open(row.id, row.title);
                }}
              />
            ))}
          </div>
        </>
      ) : null}
      {topics.dialog}
      {topUp ? (
        <TopUpDialog
          balance={profile.star_balance ?? 0}
          onClose={() => {
            setTopUp(false);
          }}
        />
      ) : null}
    </Screen>
  );
}

function reducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function PersonCard({ person }: { person: ResolvedPerson }) {
  return (
    <article className={styles.person}>
      <Avatar letters={person.initials} />
      <strong>{person.name}</strong>
      <p>{person.birthDate}</p>
      <p>{person.sign}</p>
    </article>
  );
}

function PersonSlot({
  headingId,
  legend,
  slot,
  people,
  profile,
  onChange,
  onRemember,
}: {
  headingId: string;
  legend: string;
  slot: SlotState;
  people: KnownPerson[];
  profile: ProfileResponse;
  onChange: (slot: SlotState) => void;
  onRemember: (person: KnownPerson) => void;
}) {
  const client = useQueryClient();
  const save = useMutation({
    mutationFn: () => {
      const clock = slot.time.trim();
      return addRelated(
        slot.name.trim(),
        slot.date.trim(),
        readingKey(),
        fetch,
        true,
        clock === "" ? undefined : clock,
      );
    },
    onSuccess: async (entry) => {
      const person = {
        id: entry.related_id,
        name: entry.display_name,
        birthDate: entry.birth_date ?? slot.date,
        birthTime: entry.birth_time ?? slot.time.trim(),
      };
      onRemember(person);
      onChange({ ...slot, choice: "saved", savedId: entry.related_id, save: false });
      await client.invalidateQueries({ queryKey: queryKeys.related });
    },
    onError: () => {
      onChange({ ...slot, save: false });
    },
  });
  const modes: { id: Choice; label: string }[] = [
    { id: "self", label: "Я" },
    { id: "draft", label: "Новый" },
  ];
  if (people.length > 0 || slot.choice === "saved") {
    modes.splice(1, 0, { id: "saved", label: "Близкий" });
  }
  const chosen = people.find((person) => person.id === slot.savedId);
  const ready = resolveSlot(slot, profile, people) !== null;
  const showSave =
    slot.choice === "draft" &&
    ready &&
    clockReady(slot.time) &&
    !alreadySaved(people, slot.name, slot.date);
  const summary =
    slot.choice === "self"
      ? selfSummary(profile)
      : slot.choice === "saved" && chosen !== undefined
        ? `${chosen.name} · ${displayBirthDate(chosen.birthDate)}`
        : "";
  return (
    <section className={styles.stack} aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.slotTitle}>
        {legend}
      </h2>
      <SegmentedControl
        label={legend}
        role="radiogroup"
        value={slot.choice}
        options={modes}
        onChange={(choice) => {
          if (choice === "saved" && !people.some((person) => person.id === slot.savedId)) {
            onChange({ ...slot, choice, savedId: people[0]?.id ?? "" });
            return;
          }
          onChange({ ...slot, choice });
        }}
      />
      {slot.choice === "saved" && people.length > 0 ? (
        <SegmentedControl
          label={`${legend}: близкий`}
          role="radiogroup"
          value={slot.savedId}
          options={people.map((person) => ({ id: person.id, label: person.name }))}
          onChange={(savedId) => {
            onChange({ ...slot, savedId });
          }}
        />
      ) : null}
      {summary !== "" ? <p className={styles.meta}>{summary}</p> : null}
      {slot.choice === "draft" ? (
        <>
          <Field
            label="Имя"
            chevron={false}
            value={slot.name}
            onChange={(name) => {
              onChange({ ...slot, name });
            }}
          />
          <Field
            label="Дата рождения"
            icon="date_calendar"
            chevron={false}
            value={slot.date}
            onChange={(value) => {
              onChange({ ...slot, date: maskBirthDate(value) });
            }}
          />
          <Field
            label="Время рождения"
            icon="clock"
            chevron={false}
            value={slot.time}
            onChange={(time) => {
              onChange({ ...slot, time });
            }}
          />
          {showSave ? (
            <Toggle
              label="Сохранить в близкие"
              checked={slot.save || save.isPending}
              onChange={(checked) => {
                if (!checked) {
                  onChange({ ...slot, save: false });
                  return;
                }
                onChange({ ...slot, save: true });
                save.mutate();
              }}
            />
          ) : null}
          {save.isError ? <ErrorState message="Не удалось сохранить близкого" /> : null}
        </>
      ) : null}
    </section>
  );
}

function selfSummary(profile: ProfileResponse): string {
  if (profile.display_name === null || profile.birth_date === null) {
    return "";
  }
  return `${profile.display_name} · ${displayBirthDate(profile.birth_date)}`;
}

function knownPeople(
  entries: RelatedEntry[] | undefined,
  remembered: KnownPerson[],
  personId: string | undefined,
): KnownPerson[] {
  const people = (entries ?? []).map((person) => ({
    id: person.related_id,
    name: person.display_name,
    birthDate: person.birth_date ?? "",
    birthTime: person.birth_time ?? "",
  }));
  for (const person of remembered) {
    if (!people.some((item) => item.id === person.id)) {
      people.push(person);
    }
  }
  const presets = [partnerFixture, ...peopleFixture];
  const fixture = presets.find((person) => person.id === personId);
  if (fixture !== undefined && !people.some((item) => item.id === fixture.id)) {
    people.push({
      id: fixture.id,
      name: fixture.name,
      birthDate: fixture.birthDate,
      birthTime: "",
    });
  }
  return people;
}

function resolveSlot(
  slot: SlotState,
  profile: ProfileResponse,
  people: KnownPerson[],
): ResolvedPerson | null {
  if (slot.choice === "self") {
    return resolveSelf(profile);
  }
  if (slot.choice === "saved") {
    const person = people.find((item) => item.id === slot.savedId);
    if (person === undefined) {
      return null;
    }
    return fromBirth(person.name, person.birthDate);
  }
  return fromBirth(slot.name.trim(), slot.date.trim());
}

function resolveSelf(profile: ProfileResponse): ResolvedPerson | null {
  if (profile.display_name === null || profile.birth_date === null) {
    return null;
  }
  const sign = profile.calendar_sign ?? calendarSign(profile.birth_date);
  if (sign === null) {
    return null;
  }
  return {
    initials: initialsOf(profile.display_name).slice(0, 1),
    name: profile.display_name,
    birthDate: displayBirthDate(profile.birth_date),
    sign: titled(sign),
  };
}

function fromBirth(name: string, birthDate: string): ResolvedPerson | null {
  const sign = calendarSign(birthDate);
  if (name === "" || sign === null) {
    return null;
  }
  return {
    initials: initialsOf(name).slice(0, 2),
    name,
    birthDate: displayBirthDate(birthDate),
    sign: titled(sign),
  };
}

function alreadySaved(people: KnownPerson[], name: string, date: string): boolean {
  const clean = name.trim().toLocaleLowerCase("ru");
  return people.some(
    (person) =>
      person.name.trim().toLocaleLowerCase("ru") === clean &&
      displayBirthDate(person.birthDate) === displayBirthDate(date),
  );
}

function clockReady(value: string): boolean {
  const clock = value.trim();
  return clock === "" || /^([01]\d|2[0-3]):[0-5]\d$/.test(clock);
}
