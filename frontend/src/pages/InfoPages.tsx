import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  confirmPlace,
  getMeta,
  searchPlaces,
  type PlaceHit,
  type ProfileResponse,
} from "../api/client";
import { BackHome, Button, Field } from "../components/ui/controls";
import { useDebouncedValue } from "../placeQuery";
import { homeCopy, pluralText, text, type TextKey } from "../resources";
import { readWebApp } from "../telegram";

type ScreenProps = {
  title: TextKey;
  body: string;
};

export function TextScreen({ title, body }: ScreenProps) {
  useScreenBack();
  return (
    <main className="shell">
      <section className="surface">
        <h1>{text(title)}</h1>
        <p className="lead">{body}</p>
        <BackHome />
      </section>
    </main>
  );
}

export function SettingsPage() {
  return (
    <TextScreen title="ui.settings.title" body={text("bot.settings")} />
  );
}

export function TermsPage() {
  return <TextScreen title="ui.terms.title" body={text("bot.terms")} />;
}

export function HelpPage() {
  return <TextScreen title="ui.help.title" body={text("bot.help")} />;
}

export function PaySupportPage() {
  return <TextScreen title="ui.paysupport.title" body={text("bot.paysupport")} />;
}

export function PremiumPage({ profile }: { profile: ProfileResponse }) {
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => getMeta() });
  useScreenBack();
  return (
    <main className="shell">
      <section className="surface">
        <h1>{text("ui.premium.title")}</h1>
        <p className="lead">{text("bot.premium")}</p>
        {meta.isSuccess ? (
          <>
            <p className="lead">
              {homeCopy.price_label}: {meta.data.premium_price_stars}
            </p>
            <p className="meta">{pluralText("ui.premium.questions", meta.data.assistant_questions)}</p>
          </>
        ) : null}
        {meta.isError ? (
          <Button
            label={text("ui.common.retry")}
            onClick={() => {
              void meta.refetch();
            }}
          />
        ) : null}
        {profile.is_premium ? <PlaceSearch /> : <p>{text("errors.premium_required")}</p>}
        <BackHome />
      </section>
    </main>
  );
}

function PlaceSearch() {
  const client = useQueryClient();
  const [query, setQuery] = useState("");
  const stableQuery = useDebouncedValue(query);
  const [hits, setHits] = useState<PlaceHit[]>([]);
  const [searchedQuery, setSearchedQuery] = useState("");
  const [error, setError] = useState("");
  const [searching, setSearching] = useState(false);
  return (
    <>
      <Field label={text("ui.onboarding.place_title")} value={query} onChange={setQuery} />
      <Button
        label={text("ui.common.next")}
        loading={searching}
        disabled={searching || stableQuery.trim().length < 2 || stableQuery !== query}
        onClick={() => {
          setSearching(true);
          void searchPlaces(stableQuery)
            .then((found) => {
              setHits(found);
              setSearchedQuery(stableQuery);
              setError("");
            })
            .catch(() => {
              setError(text("ui.common.error"));
            })
            .finally(() => {
              setSearching(false);
            });
        }}
      />
      <p className="meta">{text("ui.place.attribution")}</p>
      {error !== "" ? <p role="alert">{error}</p> : null}
      {hits.map((hit) => (
        <button
          key={`${hit.label}:${hit.latitude}`}
          type="button"
          className="choice"
          onClick={() => {
            void confirmPlace({
              query: searchedQuery,
              label: hit.label,
              latitude: hit.latitude,
              longitude: hit.longitude,
            }).then((next) => {
              client.setQueryData(["session"], next);
            });
          }}
        >
          {hit.label}
        </button>
      ))}
    </>
  );
}

function useScreenBack(): void {
  useEffect(() => {
    const webApp = readWebApp();
    if (webApp === null) {
      return;
    }
    webApp.showBack(() => {
      window.history.back();
    });
    return () => {
      webApp.hideBack();
    };
  }, []);
}
