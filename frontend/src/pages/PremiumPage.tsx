import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import {
  ApiRequestError,
  confirmPlace,
  createBillingOrder,
  getBilling,
  postInvoiceStatus,
  redeemGift,
  searchPlaces,
  setSubscriptionCanceled,
  startTrial,
  type BillingResponse,
  type PlaceHit,
  type ProfileResponse,
} from "../api/client";
import { BackHome, Button, ErrorState, Field, Skeleton, Toast } from "../components/ui/controls";
import { EditorialListRow, PremiumHero } from "../components/ui/editorial";
import { useDebouncedValue } from "../placeQuery";
import { formatText, pluralText, text } from "../resources";
import { invoiceGrantsPremium, openInvoice, readWebApp } from "../telegram";

export function PremiumPage({ profile }: { profile: ProfileResponse }) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const billing = useQuery({ queryKey: ["billing"], queryFn: () => getBilling() });
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [code, setCode] = useState("");
  const data = billing.data;
  useScreenBack();
  useEffect(() => {
    if (data?.premium) {
      void client.invalidateQueries({ queryKey: ["session"] });
    }
  }, [client, data?.premium]);
  useEffect(() => {
    if (data?.gift_payment_state === "success") {
      sessionStorage.removeItem(storageKey("gift"));
    }
  }, [data?.gift_payment_state]);
  useEffect(() => {
    if (data?.subscription_payment_state !== "pending" && data?.gift_payment_state !== "pending") {
      return;
    }
    const timer = window.setInterval(() => {
      void billing.refetch();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [billing, data?.gift_payment_state, data?.subscription_payment_state]);

  async function pay(kind: "subscription" | "gift") {
    setBusy(kind);
    setNotice("");
    try {
      const key = rememberKey(kind);
      let ticket = await createBillingOrder(kind, key);
      for (let attempt = 0; attempt < 5 && waiting(kind, ticket); attempt += 1) {
        await delay(1000);
        ticket = await createBillingOrder(kind, key);
      }
      const link = kind === "gift" ? ticket.gift_invoice_link : ticket.subscription_invoice_link;
      const orderId = kind === "gift" ? ticket.gift_order_id : ticket.subscription_order_id;
      if (link === null || orderId === null) {
        setNotice(text("ui.premium.unavailable"));
        client.setQueryData(["billing"], ticket);
        return;
      }
      const status = await openInvoice(link);
      if (invoiceGrantsPremium(status)) {
        throw new Error("invoice status must not grant premium");
      }
      if (status === "unavailable") {
        setNotice(text("ui.premium.unavailable"));
        return;
      }
      const next = await postInvoiceStatus(orderId, status);
      client.setQueryData(["billing"], next);
    } catch (error) {
      setNotice(error instanceof ApiRequestError && error.message !== "" ? error.message : text("ui.common.error"));
    } finally {
      setBusy("");
    }
  }

  const subscribed =
    data?.subscription_state === "active" || data?.subscription_state === "cancel_scheduled";
  return (
    <main className="shell">
      <PremiumHero
        kicker={text("ui.premium.kicker")}
        title={text("ui.premium.hero_title")}
        lead={text("ui.premium.hero_lead")}
      />
      <div className="editorial-list">
        <EditorialListRow index="01" label={text("ui.premium.benefit_1")} />
        <EditorialListRow index="02" label={text("ui.premium.benefit_2")} />
        <EditorialListRow index="03" label={text("ui.premium.benefit_3")} />
      </div>
      {billing.isPending ? <Skeleton /> : null}
      {data ? (
        <>
          <p className="price-line">
            {formatText("ui.premium.price_line", {
              price: String(data.price_stars),
              days: String(data.period_days),
            })}
          </p>
          <p>{text("ui.premium.renew_line")}</p>
          <p>{pluralText("ui.premium.questions", data.assistant_questions)}</p>
        </>
      ) : null}
        <StateLine state={data?.subscription_payment_state ?? "none"} />
        {data !== undefined && subscribed ? (
          <section>
            <h2>{text("ui.premium.manage_title")}</h2>
            {data.period_end ? (
              <p>{formatText("ui.premium.active_until", { date: formatDay(data.period_end) })}</p>
            ) : null}
            {data.subscription_state === "cancel_scheduled" ? (
              <>
                <p>{text("ui.premium.cancel_note")}</p>
                <p>{text("ui.premium.resume_note")}</p>
                <Button
                  tone="outline"
                  label={text("ui.premium.resume")}
                  loading={busy === "resume"}
                  onClick={() => {
                    void changeRenewal(false);
                  }}
                />
              </>
            ) : (
              <>
                <p>{text("ui.premium.cancel_note")}</p>
                <Button
                  tone="outline"
                  label={text("ui.premium.cancel")}
                  loading={busy === "cancel"}
                  onClick={() => {
                    void changeRenewal(true);
                  }}
                />
              </>
            )}
          </section>
        ) : (
          <div className="stack">
            <Button
              label={text("ui.premium.pay")}
              loading={busy === "subscription"}
              onClick={() => {
                void pay("subscription");
              }}
            />
          </div>
        )}
        {data?.subscription_payment_state === "pending" || data?.subscription_payment_state === "failed" ? (
          <Button
            tone="outline"
            label={text("ui.premium.retry")}
            onClick={() => {
              void billing.refetch();
            }}
          />
        ) : null}
        <h2>{text("ui.premium.gift_buy")}</h2>
        <p>{text("ui.premium.gift_line")}</p>
        <StateLine state={data?.gift_payment_state ?? "none"} />
        {data?.gift_code ? (
          <>
            <p>{text("ui.premium.gift_ready")}</p>
            <p>{data.gift_code}</p>
            {data.gift_link ? <p>{data.gift_link}</p> : null}
          </>
        ) : null}
        <div className="stack">
          <Button
            tone="outline"
            icon="gift"
            label={text("ui.premium.gift_buy")}
            loading={busy === "gift"}
            onClick={() => {
              void pay("gift");
            }}
          />
          <Field label={text("ui.premium.gift_code_label")} value={code} onChange={setCode} />
          <Button
            tone="outline"
            label={text("ui.premium.gift_redeem")}
            loading={busy === "redeem"}
            onClick={() => {
              void activate();
            }}
          />
          {data?.trial_available ? (
            <Button
              tone="outline"
              label={text("ui.premium.trial")}
              loading={busy === "trial"}
              onClick={() => {
                void trial();
              }}
            />
          ) : null}
          <Button
            tone="outline"
            label={text("ui.premium.terms")}
            onClick={() => {
              navigate("/terms");
            }}
          />
          <Button
            tone="outline"
            label={text("ui.premium.support")}
            onClick={() => {
              navigate("/paysupport");
            }}
          />
        </div>
        <Toast message={notice} />
        {billing.isError ? (
          <ErrorState
            message={text("ui.common.error")}
            onRetry={() => {
              void billing.refetch();
            }}
          />
        ) : null}
        {profile.is_premium || data?.premium ? <PlaceSearch /> : null}
        <BackHome />
    </main>
  );

  async function changeRenewal(isCanceled: boolean) {
    setBusy(isCanceled ? "cancel" : "resume");
    setNotice("");
    try {
      const next = await setSubscriptionCanceled(isCanceled);
      client.setQueryData(["billing"], next);
    } catch (error) {
      setNotice(error instanceof ApiRequestError && error.message !== "" ? error.message : text("ui.common.error"));
    } finally {
      setBusy("");
    }
  }

  async function activate() {
    setBusy("redeem");
    setNotice("");
    try {
      const next = await redeemGift(code);
      client.setQueryData(["billing"], next);
      void client.invalidateQueries({ queryKey: ["session"] });
      setCode("");
    } catch (error) {
      setNotice(error instanceof ApiRequestError && error.message !== "" ? error.message : text("ui.common.error"));
    } finally {
      setBusy("");
    }
  }

  async function trial() {
    setBusy("trial");
    setNotice("");
    try {
      const next = await startTrial();
      client.setQueryData(["billing"], next);
      void client.invalidateQueries({ queryKey: ["session"] });
    } catch (error) {
      setNotice(error instanceof ApiRequestError && error.message !== "" ? error.message : text("ui.common.error"));
    } finally {
      setBusy("");
    }
  }
}

function StateLine({ state }: { state: string }) {
  if (state === "pending") {
    return <p role="status">{text("ui.premium.pending")}</p>;
  }
  if (state === "success") {
    return <p role="status">{text("ui.premium.success")}</p>;
  }
  if (state === "canceled") {
    return <p role="status">{text("ui.premium.canceled")}</p>;
  }
  if (state === "failed") {
    return <p role="status">{text("ui.premium.failed")}</p>;
  }
  return null;
}

function waiting(kind: "subscription" | "gift", ticket: BillingResponse): boolean {
  const link = kind === "gift" ? ticket.gift_invoice_link : ticket.subscription_invoice_link;
  const state = kind === "gift" ? ticket.gift_payment_state : ticket.subscription_payment_state;
  return link === null && state === "pending";
}

function storageKey(kind: string): string {
  return `starflow-invoice-${kind}`;
}

function rememberKey(kind: string): string {
  const key = storageKey(kind);
  const existing = sessionStorage.getItem(key);
  if (existing !== null && existing.length >= 8) {
    return existing;
  }
  const created = crypto.randomUUID().replaceAll("-", "");
  sessionStorage.setItem(key, created);
  return created;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function formatDay(iso: string): string {
  return new Intl.DateTimeFormat("ru", { day: "numeric", month: "long", year: "numeric" }).format(
    new Date(iso),
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
