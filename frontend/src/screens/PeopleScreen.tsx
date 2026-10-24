import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { addRelated, getRelated, readingKey } from "../api/client";
import { queryKeys } from "../api/keys";
import { Button } from "../shared/ui/Button/Button";
import { Field } from "../shared/ui/Field/Field";
import { ListRow } from "../shared/ui/ListRow/ListRow";
import { Screen } from "../shared/ui/Screen/Screen";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import { initialsOf } from "./format";
import styles from "./screens.module.css";

export function PeopleScreen() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [born, setBorn] = useState("");
  const related = useQuery({ queryKey: queryKeys.related, queryFn: () => getRelated() });
  const add = useMutation({
    mutationFn: () => addRelated(name, born, readingKey(), fetch, true),
    onSuccess: async () => {
      setAdding(false);
      setName("");
      setBorn("");
      await client.invalidateQueries({ queryKey: queryKeys.related });
    },
  });
  const rows = (related.data ?? []).map((person) => ({
    id: person.related_id,
    initials: initialsOf(person.display_name),
    name: person.display_name,
    birthDate: person.birth_date ?? "",
  }));
  return (
    <Screen tab="profile">
      <TopBar title="Близкие" align="left" back />
      <div className={styles.stack}>
        {rows.map((person) => (
          <ListRow
            key={person.id}
            avatar={person.initials}
            title={person.name}
            subtitle={person.birthDate}
            chevron
            onClick={() => {
              void navigate(`/compatibility/${person.id}`);
            }}
          />
        ))}
      </div>
      {adding ? (
        <div className={styles.stack}>
          <Field label="Имя" value={name} chevron={false} onChange={setName} />
          <Field label="Дата рождения" value={born} chevron={false} onChange={setBorn} />
          <Button
            disabled={name.trim() === "" || born.trim() === ""}
            onClick={() => {
              add.mutate();
            }}
          >
            Сохранить
          </Button>
        </div>
      ) : null}
      <Button
        variant="secondary"
        icon="user_add"
        onClick={() => {
          setAdding(true);
        }}
      >
        Добавить человека
      </Button>
    </Screen>
  );
}
