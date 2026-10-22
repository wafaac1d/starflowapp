import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import {
  addRelated,
  getFavorites,
  getHistory,
  getReferral,
  getRelated,
  readingKey,
} from "../api/client";
import { BackHome, Button, EmptyState, Field, Skeleton } from "../components/ui/controls";
import { EditorialListRow } from "../components/ui/editorial";
import { text } from "../resources";

type FetchProps = {
  fetchImpl?: typeof fetch;
};

export function HistoryPage({ fetchImpl = fetch }: FetchProps) {
  const history = useQuery({ queryKey: ["history"], queryFn: () => getHistory(fetchImpl) });
  return (
    <main className="shell">
      <h1>{text("ui.reading.history")}</h1>
      {history.isPending ? <Skeleton /> : null}
      {history.data !== undefined && history.data.length === 0 ? (
        <EmptyState title={text("ui.empty.history")} />
      ) : null}
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
      {favorites.isPending ? <Skeleton /> : null}
      {favorites.data !== undefined && favorites.data.length === 0 ? (
        <EmptyState title={text("ui.empty.favorites")} />
      ) : null}
      {favorites.data?.map((item) => (
        <p key={item.history_id}>{item.title}</p>
      ))}
      <BackHome />
    </main>
  );
}

export function RelatedPage({ fetchImpl = fetch }: FetchProps) {
  const navigate = useNavigate();
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
      <EditorialListRow
        label={text("ui.reading.compatibility")}
        arrow
        onClick={() => {
          void navigate("/reading/compatibility");
        }}
      />
      {related.isPending ? <Skeleton /> : null}
      {related.data !== undefined && related.data.length === 0 ? (
        <EmptyState title={text("ui.empty.related")} />
      ) : null}
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
