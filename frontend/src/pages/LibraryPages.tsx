import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  addRelated,
  getFavorites,
  getHistory,
  getReferral,
  getRelated,
  readingKey,
} from "../api/client";
import { BackHome, Button, Field } from "../components/ui/controls";
import { text } from "../resources";

type FetchProps = {
  fetchImpl?: typeof fetch;
};

export function HistoryPage({ fetchImpl = fetch }: FetchProps) {
  const history = useQuery({ queryKey: ["history"], queryFn: () => getHistory(fetchImpl) });
  return (
    <main className="shell">
      <h1>{text("ui.reading.history")}</h1>
      {history.data?.map((item) => (
        <p key={item.history_id}>
          {item.title} · {item.period_date}
        </p>
      ))}
      <BackHome />
    </main>
  );
}

export function FavoritesPage({ fetchImpl = fetch }: FetchProps) {
  const favorites = useQuery({ queryKey: ["favorites"], queryFn: () => getFavorites(fetchImpl) });
  return (
    <main className="shell">
      <h1>{text("ui.reading.favorites")}</h1>
      {favorites.data?.map((item) => (
        <p key={item.history_id}>{item.title}</p>
      ))}
      <BackHome />
    </main>
  );
}

export function RelatedPage({ fetchImpl = fetch }: FetchProps) {
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [born, setBorn] = useState("");
  const related = useQuery({ queryKey: ["related"], queryFn: () => getRelated(fetchImpl) });
  const add = useMutation({
    mutationFn: () => addRelated(name, born, readingKey(), fetchImpl),
    onSuccess: async () => {
      setName("");
      setBorn("");
      await client.invalidateQueries({ queryKey: ["related"] });
    },
  });
  return (
    <main className="shell">
      <h1>{text("ui.reading.related")}</h1>
      {related.data?.map((item) => (
        <p key={item.related_id}>
          {item.display_name}
          {item.birth_date === null ? "" : ` · ${item.birth_date}`}
        </p>
      ))}
      <Field label={text("ui.onboarding.name_title")} value={name} onChange={setName} />
      <Field label={text("ui.onboarding.date_title")} value={born} onChange={setBorn} />
      <Button
        label={text("ui.reading.add_related")}
        onClick={() => {
          add.mutate();
        }}
      />
      {add.isError ? <p role="alert">{text("ui.common.error")}</p> : null}
      <BackHome />
    </main>
  );
}

export function ReferralPage({ fetchImpl = fetch }: FetchProps) {
  const referral = useQuery({ queryKey: ["referral"], queryFn: () => getReferral(fetchImpl) });
  return (
    <main className="shell">
      <h1>{text("ui.reading.referral")}</h1>
      {referral.data !== undefined ? (
        <>
          <p>{referral.data.code}</p>
          <p className="reading-copy">{referral.data.link}</p>
        </>
      ) : null}
      <BackHome />
    </main>
  );
}
