import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import {
  addRelated,
  allowRelated,
  deleteRelated,
  getHistory,
  getReferral,
  getRelated,
  readingKey,
} from "../api/client";
import { BackHome, Button, EmptyState, ErrorState, Field, Skeleton } from "../components/ui/controls";
import { CompatibilityEntry, EditorialListRow, PageHeader } from "../components/ui/editorial";
import { ReferralScreen } from "../screens/ReferralScreen";
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

export function RelatedPage({ fetchImpl = fetch }: FetchProps) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [born, setBorn] = useState("");
  const [consent, setConsent] = useState(false);
  const related = useQuery({ queryKey: ["related"], queryFn: () => getRelated(fetchImpl) });
  const add = useMutation({
    mutationFn: () => addRelated(name, born, readingKey(), fetchImpl, consent),
    onSuccess: async () => {
      setName("");
      setBorn("");
      setConsent(false);
      setAdding(false);
      await client.invalidateQueries({ queryKey: ["related"] });
    },
  });
  return (
    <main className="shell page">
      <h1 className="page-title">{text("ui.reading.related")}</h1>
      <p className="lead">{text("ui.reading.circle")}</p>
      {related.isPending ? <Skeleton /> : null}
      {related.isError ? (
        <ErrorState
          message={text("ui.common.error")}
          onRetry={() => {
            void related.refetch();
          }}
        />
      ) : null}
      {related.data !== undefined && related.data.length === 0 ? (
        <EmptyState title={text("ui.empty.related")} />
      ) : null}
      <div className="editorial-list">
        {related.data?.map((item) => (
          <div key={item.related_id}>
            <EditorialListRow
              icon="people"
              typed
              label={item.display_name}
              {...(item.birth_date !== null ? { hint: item.birth_date } : {})}
              arrow={item.consent === true}
              {...(item.consent === true
                ? {
                    onClick: () => {
                      void navigate(`/reading/synastry?related_id=${item.related_id}`);
                    },
                  }
                : {})}
            />
            {item.consent ? null : (
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  void allowRelated(item.related_id, fetchImpl).then(() =>
                    client.invalidateQueries({ queryKey: ["related"] }),
                  );
                }}
              >
                {text("ui.synastry.allow")}
              </button>
            )}
            <button
              type="button"
              className="text-button"
              onClick={() => {
                void deleteRelated(item.related_id, fetchImpl).then(() =>
                  client.invalidateQueries({ queryKey: ["related"] }),
                );
              }}
            >
              {text("ui.synastry.remove")}
            </button>
          </div>
        ))}
      </div>
      {adding ? (
        <>
          <Field label={text("ui.onboarding.name_title")} value={name} onChange={setName} />
          <Field label={text("ui.onboarding.date_title")} value={born} onChange={setBorn} />
          <label className="consent-row">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => {
                setConsent(event.target.checked);
              }}
            />
            {text("ui.synastry.consent")}
          </label>
          <Button
            label={text("ui.reading.add_person")}
            disabled={!consent || name.trim() === "" || born.trim() === "" || add.isPending}
            onClick={() => {
              add.mutate();
            }}
          />
          <Button
            tone="outline"
            label={text("ui.common.cancel")}
            onClick={() => {
              setAdding(false);
            }}
          />
        </>
      ) : (
        <Button
          tone="outline"
          label={text("ui.reading.add_person")}
          onClick={() => {
            setAdding(true);
          }}
        />
      )}
      {add.isError ? <p role="alert">{text("ui.common.error")}</p> : null}
      <CompatibilityEntry
        title={text("ui.reading.compat_title")}
        lead={text("ui.reading.compat_lead")}
        onClick={() => {
          void navigate("/reading/compatibility");
        }}
      />
    </main>
  );
}

export function ReferralPage({ fetchImpl = fetch }: FetchProps) {
  return <ReferralScreen fetchImpl={fetchImpl} />;
}
