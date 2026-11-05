import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useLocation } from "react-router";

import {
  ApiRequestError,
  addRelated,
  deleteRelated,
  getRelated,
  readingKey,
  updateRelated,
  type RelatedEntry,
} from "../api/client";
import { queryKeys } from "../api/keys";
import { maskBirthDate } from "../birthDate";
import { displayBirthDate } from "../calendarSign";
import { Button } from "../shared/ui/Button/Button";
import { Field } from "../shared/ui/Field/Field";
import { ListRow } from "../shared/ui/ListRow/ListRow";
import { Screen } from "../shared/ui/Screen/Screen";
import { Skeleton } from "../shared/ui/Skeleton/Skeleton";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import { initialsOf } from "./format";
import styles from "./screens.module.css";

const FREE_RELATED = 2;
const PREMIUM_RELATED = 10;

type Editor =
  | { kind: "closed" }
  | { kind: "add" }
  | { kind: "edit"; id: string; birthTime: string };

export function PeopleScreen({ premium = false }: { premium?: boolean }) {
  const location = useLocation();
  const client = useQueryClient();
  const [editor, setEditor] = useState<Editor>(() =>
    wantsAdd(location.state) ? { kind: "add" } : { kind: "closed" },
  );
  const [name, setName] = useState("");
  const [born, setBorn] = useState("");
  const [notice, setNotice] = useState("");
  const related = useQuery({ queryKey: queryKeys.related, queryFn: () => getRelated() });
  const people = related.data ?? [];
  const limit = premium ? PREMIUM_RELATED : FREE_RELATED;
  const full = people.length >= limit;
  const save = useMutation({
    mutationFn: () => {
      if (editor.kind === "edit") {
        if (editor.birthTime !== "") {
          return updateRelated(editor.id, name, born, fetch, editor.birthTime);
        }
        return updateRelated(editor.id, name, born);
      }
      return addRelated(name, born, readingKey(), fetch, true);
    },
    onSuccess: async () => {
      setEditor({ kind: "closed" });
      setName("");
      setBorn("");
      setNotice("");
      await client.invalidateQueries({ queryKey: queryKeys.related });
    },
    onError: (error) => {
      setNotice(error instanceof ApiRequestError && error.message !== "" ? error.message : "Не удалось сохранить");
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteRelated(id),
    onSuccess: async () => {
      setEditor({ kind: "closed" });
      setName("");
      setBorn("");
      setNotice("");
      await client.invalidateQueries({ queryKey: queryKeys.related });
    },
    onError: () => {
      setNotice("Не удалось удалить");
    },
  });
  const formOpen = editor.kind !== "closed" && !(editor.kind === "add" && full);

  return (
    <Screen tab="profile">
      <TopBar title="Близкие" align="left" back />
      <div className={styles.people}>
        {related.isPending ? <Skeleton lines={3} variant="rows" /> : null}
        {related.isSuccess
          ? people.map((person) => (
              <ListRow
                key={person.related_id}
                avatar={initialsOf(person.display_name)}
                title={person.display_name}
                subtitle={person.birth_date === null ? "" : displayBirthDate(person.birth_date)}
                chevron
                onClick={() => {
                  openPerson(person);
                }}
              />
            ))
          : null}
        {full && editor.kind !== "edit" ? (
          <p className={styles.paragraph}>
            {premium
              ? "В списке уже десять близких."
              : "Можно хранить двух близких. С Premium — до десяти."}
          </p>
        ) : null}
        {formOpen ? (
          <>
            <Field label="Имя" value={name} chevron={false} onChange={setName} />
            <Field
              label="Дата рождения"
              value={born}
              chevron={false}
              inputMode="numeric"
              onChange={(value) => setBorn((prev) => maskBirthDate(value, prev))}
            />
            {notice !== "" ? <p role="alert">{notice}</p> : null}
            <Button
              disabled={name.trim() === "" || born.trim() === ""}
              loading={save.isPending}
              onClick={() => {
                save.mutate();
              }}
            >
              Сохранить
            </Button>
            {editor.kind === "edit" ? (
              <Button
                variant="secondary"
                loading={remove.isPending}
                onClick={() => {
                  remove.mutate(editor.id);
                }}
              >
                Удалить
              </Button>
            ) : null}
          </>
        ) : null}
        <Button
          variant="secondary"
          icon="user_add"
          disabled={full}
          onClick={() => {
            if (full) {
              return;
            }
            setEditor({ kind: "add" });
            setName("");
            setBorn("");
            setNotice("");
          }}
        >
          Добавить человека
        </Button>
      </div>
    </Screen>
  );

  function openPerson(person: RelatedEntry) {
    const knownTime = person.birth_time_unknown === false && person.birth_time != null;
    setEditor({
      kind: "edit",
      id: person.related_id,
      birthTime: knownTime ? person.birth_time ?? "" : "",
    });
    setName(person.display_name);
    setBorn(person.birth_date === null ? "" : displayBirthDate(person.birth_date));
    setNotice("");
  }
}

function wantsAdd(state: unknown): boolean {
  return isRecord(state) && state.add === true;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
