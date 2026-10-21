import type { paths } from "./schema";

export type MetaResponse =
  paths["/api/v1/meta"]["get"]["responses"][200]["content"]["application/json"];

export type ProfileResponse = {
  user_id: string;
  is_admin: boolean;
  is_premium: boolean;
  step: string;
  display_name: string | null;
  birth_date: string | null;
  birth_time: string | null;
  birth_time_unknown: boolean;
  timezone: string | null;
  birth_place: string | null;
  latitude: string | null;
  longitude: string | null;
  calendar_sign: string | null;
};

export type PlaceHit = {
  label: string;
  latitude: string;
  longitude: string;
};

export class ApiRequestError extends Error {
  readonly status: number;
  readonly fields: Record<string, string>;

  constructor(status: number, message: string, fields: Record<string, string>) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

export type DraftPayload = {
  display_name?: string;
  birth_date?: string;
  birth_time?: string;
  birth_time_unknown?: boolean;
  timezone?: string;
};

export async function getMeta(fetchImpl: typeof fetch = fetch): Promise<MetaResponse> {
  return requestJson<MetaResponse>("/api/v1/meta", { method: "GET" }, fetchImpl);
}

export async function openSession(
  initData: string,
  fetchImpl: typeof fetch = fetch,
): Promise<ProfileResponse> {
  return requestJson<ProfileResponse>(
    "/api/v1/session",
    {
      method: "POST",
      headers: { Authorization: `TMA ${initData}` },
    },
    fetchImpl,
  );
}

export async function saveDraft(
  body: DraftPayload,
  fetchImpl: typeof fetch = fetch,
): Promise<ProfileResponse> {
  return requestJson<ProfileResponse>(
    "/api/v1/profile/draft",
    { method: "POST", body: JSON.stringify(body) },
    fetchImpl,
  );
}

export async function stepBack(fetchImpl: typeof fetch = fetch): Promise<ProfileResponse> {
  return requestJson<ProfileResponse>("/api/v1/profile/back", { method: "POST" }, fetchImpl);
}

export async function editProfile(
  body: DraftPayload,
  fetchImpl: typeof fetch = fetch,
): Promise<ProfileResponse> {
  return requestJson<ProfileResponse>(
    "/api/v1/profile",
    { method: "PATCH", body: JSON.stringify(body) },
    fetchImpl,
  );
}

export async function searchPlaces(
  query: string,
  fetchImpl: typeof fetch = fetch,
): Promise<PlaceHit[]> {
  return requestJson<PlaceHit[]>(
    "/api/v1/places/search",
    { method: "POST", body: JSON.stringify({ query }) },
    fetchImpl,
  );
}

export async function confirmPlace(
  body: { query: string; label: string; latitude: string; longitude: string },
  fetchImpl: typeof fetch = fetch,
): Promise<ProfileResponse> {
  return requestJson<ProfileResponse>(
    "/api/v1/profile/place",
    { method: "POST", body: JSON.stringify(body) },
    fetchImpl,
  );
}

export type PlanetPlacement = {
  name: string;
  longitude: number;
  sign: string | null;
  element: string | null;
  modality: string | null;
  ruler: string | null;
  decan: number | null;
  decan_ruler: string | null;
  retrograde: boolean;
  exact: boolean;
};

export type ChartResponse = {
  sun_sign: string | null;
  sun_sign_source: string;
  moon_sign: string | null;
  ascendant_sign: string | null;
  houses: string[] | null;
  planets: PlanetPlacement[];
  aspects: string[];
  transits: string[];
  lunar_day: number | null;
  phase_name: string | null;
  limitations: string[];
  natal_access: string;
};

export type SkyResponse = {
  sun_sign: string;
  moon_sign: string;
  phase_name: string;
  bodies: PlanetPlacement[];
};

export async function getChart(fetchImpl: typeof fetch = fetch): Promise<ChartResponse> {
  return requestJson<ChartResponse>("/api/v1/chart", { method: "GET" }, fetchImpl);
}

export async function getSky(fetchImpl: typeof fetch = fetch): Promise<SkyResponse> {
  return requestJson<SkyResponse>("/api/v1/sky", { method: "GET" }, fetchImpl);
}

export async function deleteProfile(fetchImpl: typeof fetch = fetch): Promise<void> {
  await requestJson<unknown>("/api/v1/profile", { method: "DELETE" }, fetchImpl);
}

export type ReadingResponse = {
  status: string;
  title: string | null;
  body: string | null;
  greeting: string | null;
  user_sign: string | null;
  shared_facts: string | null;
  history_id: string | null;
  streak: number | null;
  replayed: boolean;
  reset_at: string | null;
};

export type HistoryEntry = {
  history_id: string;
  kind: string;
  period_date: string;
  title: string;
};

export type FavoriteEntry = {
  history_id: string;
  title: string;
};

export type RelatedEntry = {
  related_id: string;
  display_name: string;
  birth_date: string | null;
};

export type ReferralResponse = {
  code: string;
  link: string;
};

export async function startReading(
  kind: string,
  idempotencyKey: string,
  fetchImpl: typeof fetch = fetch,
): Promise<ReadingResponse> {
  return requestJson<ReadingResponse>(
    `/api/v1/readings/${kind}`,
    { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
    fetchImpl,
  );
}

export async function getReading(
  kind: string,
  fetchImpl: typeof fetch = fetch,
): Promise<ReadingResponse> {
  return requestJson<ReadingResponse>(`/api/v1/readings/${kind}`, { method: "GET" }, fetchImpl);
}

export async function sendFeedback(
  historyId: string,
  score: number,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  await requestJson<unknown>(
    `/api/v1/readings/${historyId}/feedback`,
    { method: "POST", body: JSON.stringify({ score }) },
    fetchImpl,
  );
}

export async function getShare(historyId: string, fetchImpl: typeof fetch = fetch): Promise<string> {
  const payload = await requestJson<{ text: string }>(
    `/api/v1/share/${historyId}`,
    { method: "GET" },
    fetchImpl,
  );
  return payload.text;
}

export async function getHistory(fetchImpl: typeof fetch = fetch): Promise<HistoryEntry[]> {
  return requestJson<HistoryEntry[]>("/api/v1/history", { method: "GET" }, fetchImpl);
}

export async function getFavorites(fetchImpl: typeof fetch = fetch): Promise<FavoriteEntry[]> {
  return requestJson<FavoriteEntry[]>("/api/v1/favorites", { method: "GET" }, fetchImpl);
}

export async function saveFavorite(
  historyId: string,
  idempotencyKey: string,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  await requestJson<unknown>(
    "/api/v1/favorites",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ target_id: historyId }),
    },
    fetchImpl,
  );
}

export async function getRelated(fetchImpl: typeof fetch = fetch): Promise<RelatedEntry[]> {
  return requestJson<RelatedEntry[]>("/api/v1/related", { method: "GET" }, fetchImpl);
}

export async function addRelated(
  displayName: string,
  birthDate: string,
  idempotencyKey: string,
  fetchImpl: typeof fetch = fetch,
): Promise<RelatedEntry> {
  return requestJson<RelatedEntry>(
    "/api/v1/related",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ display_name: displayName, birth_date: birthDate }),
    },
    fetchImpl,
  );
}

export async function getReferral(fetchImpl: typeof fetch = fetch): Promise<ReferralResponse> {
  return requestJson<ReferralResponse>("/api/v1/referral", { method: "GET" }, fetchImpl);
}

export type BillingResponse = {
  premium: boolean;
  access_until: string | null;
  price_stars: number;
  period_days: number;
  gift_days: number;
  trial_days: number;
  assistant_questions: number;
  subscription_payment_state: string;
  gift_payment_state: string;
  subscription_state: string;
  auto_renew: boolean;
  subscription_order_id: string | null;
  subscription_invoice_link: string | null;
  gift_order_id: string | null;
  gift_invoice_link: string | null;
  gift_code: string | null;
  gift_link: string | null;
  trial_available: boolean;
  period_end: string | null;
};

export async function getBilling(fetchImpl: typeof fetch = fetch): Promise<BillingResponse> {
  return requestJson<BillingResponse>("/api/v1/billing", { method: "GET" }, fetchImpl);
}

export async function createBillingOrder(
  kind: "subscription" | "gift",
  idempotencyKey: string,
  fetchImpl: typeof fetch = fetch,
): Promise<BillingResponse> {
  return requestJson<BillingResponse>(
    "/api/v1/billing/orders",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ kind }),
    },
    fetchImpl,
  );
}

export async function postInvoiceStatus(
  orderId: string,
  status: string,
  fetchImpl: typeof fetch = fetch,
): Promise<BillingResponse> {
  return requestJson<BillingResponse>(
    `/api/v1/billing/orders/${orderId}/client-status`,
    { method: "POST", body: JSON.stringify({ status }) },
    fetchImpl,
  );
}

export async function setSubscriptionCanceled(
  isCanceled: boolean,
  fetchImpl: typeof fetch = fetch,
): Promise<BillingResponse> {
  return requestJson<BillingResponse>(
    "/api/v1/billing/subscription",
    { method: "POST", body: JSON.stringify({ is_canceled: isCanceled }) },
    fetchImpl,
  );
}

export async function startTrial(fetchImpl: typeof fetch = fetch): Promise<BillingResponse> {
  return requestJson<BillingResponse>("/api/v1/billing/trial", { method: "POST" }, fetchImpl);
}

export async function redeemGift(
  code: string,
  fetchImpl: typeof fetch = fetch,
): Promise<BillingResponse> {
  return requestJson<BillingResponse>(
    "/api/v1/billing/gifts/redeem",
    { method: "POST", body: JSON.stringify({ code }) },
    fetchImpl,
  );
}

export function readingKey(): string {
  const stamp = Date.now().toString(36);
  const salt = Math.random().toString(36).slice(2, 12);
  return `read${stamp}${salt}`;
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
  fetchImpl: typeof fetch,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (init.method !== undefined && init.method !== "GET") {
    headers.set("X-Starflow-Request", "1");
  }
  const response = await fetchImpl(path, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    throw await readFailure(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function readFailure(response: Response): Promise<ApiRequestError> {
  let message = "";
  let fields: Record<string, string> = {};
  try {
    const payload: unknown = await response.json();
    if (typeof payload === "object" && payload !== null) {
      const record = payload as { error?: { message?: unknown }; fields?: unknown };
      if (typeof record.error?.message === "string") {
        message = record.error.message;
      }
      if (typeof record.fields === "object" && record.fields !== null) {
        fields = Object.fromEntries(
          Object.entries(record.fields).filter((entry): entry is [string, string] => {
            return typeof entry[1] === "string";
          }),
        );
      }
    }
  } catch {
    message = "";
  }
  return new ApiRequestError(response.status, message, fields);
}
