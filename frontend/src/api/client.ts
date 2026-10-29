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
  star_balance: number;
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
  house_cusps: number[] | null;
  planets: PlanetPlacement[];
  aspects: string[];
  transits: string[];
  lunar_day: number | null;
  phase_name: string | null;
  limitations: string[];
  natal_access: string;
  sections?: ChartSection[];
};

export type ChartSection = {
  id: string;
  title: string;
  body: string;
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
  days?: CalendarDay[];
  limitations?: string[];
};

export type CalendarDay = {
  date: string;
  scores: Record<string, number>;
  note: string;
};

export type ReadingQuery = {
  topic?: string;
  month?: string;
  relatedId?: string;
  leftSign?: string;
  rightSign?: string;
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

export type FavoriteReading = {
  history_id: string;
  title: string;
  body: string;
};

export type RelatedEntry = {
  related_id: string;
  display_name: string;
  birth_date: string | null;
  birth_time?: string | null;
  birth_time_unknown?: boolean;
  consent?: boolean;
};

export type ReferralResponse = {
  code: string;
  link: string;
};

export async function startReading(
  kind: string,
  idempotencyKey: string,
  fetchImpl: typeof fetch = fetch,
  query: ReadingQuery = {},
): Promise<ReadingResponse> {
  return requestJson<ReadingResponse>(
    readingPath(kind, query),
    { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
    fetchImpl,
  );
}

export async function getReading(
  kind: string,
  fetchImpl: typeof fetch = fetch,
  query: ReadingQuery = {},
): Promise<ReadingResponse> {
  return requestJson<ReadingResponse>(readingPath(kind, query), { method: "GET" }, fetchImpl);
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

export async function getFavoriteReading(
  historyId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<FavoriteReading> {
  return requestJson<FavoriteReading>(
    `/api/v1/favorites/${historyId}`,
    { method: "GET" },
    fetchImpl,
  );
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
  consent = false,
  birthTime?: string,
): Promise<RelatedEntry> {
  const clock = birthTime?.trim() ?? "";
  const body: {
    display_name: string;
    birth_date: string;
    consent: boolean;
    birth_time_unknown: boolean;
    birth_time?: string;
  } = {
    display_name: displayName,
    birth_date: birthDate,
    consent,
    birth_time_unknown: clock === "",
  };
  if (clock !== "") {
    body.birth_time = clock;
  }
  return requestJson<RelatedEntry>(
    "/api/v1/related",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(body),
    },
    fetchImpl,
  );
}

export async function allowRelated(
  relatedId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  await requestJson<unknown>(`/api/v1/related/${relatedId}/consent`, { method: "POST" }, fetchImpl);
}

export async function deleteRelated(
  relatedId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  await requestJson<unknown>(`/api/v1/related/${relatedId}`, { method: "DELETE" }, fetchImpl);
}

export type NoticePrefs = {
  local_time: string;
  timezone: string;
  day: boolean;
  moon: boolean;
  retro: boolean;
};

export const NOTICE_SLOTS: readonly string[] = Array.from({ length: 48 }, (_, index) => {
  const hour = Math.floor(index / 2)
    .toString()
    .padStart(2, "0");
  const minute = index % 2 === 0 ? "00" : "30";
  return `${hour}:${minute}`;
});

export async function getNotifications(fetchImpl: typeof fetch = fetch): Promise<NoticePrefs> {
  return requestJson<NoticePrefs>("/api/v1/notifications", { method: "GET" }, fetchImpl);
}

export async function saveNotifications(
  body: NoticePrefs,
  fetchImpl: typeof fetch = fetch,
): Promise<NoticePrefs> {
  return requestJson<NoticePrefs>(
    "/api/v1/notifications",
    { method: "PUT", body: JSON.stringify(body) },
    fetchImpl,
  );
}

export type RetroPeriod = {
  planet: string;
  start: string;
  end: string;
};

export async function getRetro(fetchImpl: typeof fetch = fetch): Promise<RetroPeriod[]> {
  return requestJson<RetroPeriod[]>("/api/v1/retro", { method: "GET" }, fetchImpl);
}

export type FavorableDay = {
  date: string;
  start: string;
  end: string;
  note: string;
};

export type FavorableMonth = {
  status: string;
  event: string;
  label: string;
  month: string;
  timezone: string;
  access: string;
  price: number;
  days: FavorableDay[];
  free_chosen_label?: string | null;
};

export type FavorableStatus = {
  chosen_event: string | null;
  chosen_custom: string | null;
  chosen_label: string | null;
  is_premium: boolean;
};

export async function getFavorableStatus(
  fetchImpl: typeof fetch = fetch,
): Promise<FavorableStatus> {
  return requestJson<FavorableStatus>("/api/v1/favorable/status", { method: "GET" }, fetchImpl);
}

export async function getFavorable(
  month: string,
  event: string,
  custom = "",
  fetchImpl: typeof fetch = fetch,
): Promise<FavorableMonth> {
  const params = new URLSearchParams({ month, event });
  if (event === "custom" && custom !== "") {
    params.set("custom", custom);
  }
  return requestJson<FavorableMonth>(
    `/api/v1/favorable?${params.toString()}`,
    { method: "GET" },
    fetchImpl,
  );
}

export type AffirmationCard = {
  id: string;
  text: string;
  category: string;
  bg_image: string;
};

export type AffirmationsResponse = {
  category: string;
  label: string;
  access: string;
  price: number;
  cards: AffirmationCard[];
  free_chosen_label?: string | null;
};

export type AffirmationsStatus = {
  chosen_category: string | null;
  chosen_label: string | null;
  is_premium: boolean;
};

export async function getAffirmations(
  category = "for_you",
  fetchImpl: typeof fetch = fetch,
): Promise<AffirmationsResponse> {
  return requestJson<AffirmationsResponse>(
    `/api/v1/affirmations?category=${encodeURIComponent(category)}`,
    { method: "GET" },
    fetchImpl,
  );
}

export async function getAffirmationsStatus(
  fetchImpl: typeof fetch = fetch,
): Promise<AffirmationsStatus> {
  return requestJson<AffirmationsStatus>(
    "/api/v1/affirmations/status",
    { method: "GET" },
    fetchImpl,
  );
}

export type SupportTicket = {
  id: string;
  subject: string;
  message: string;
  status: string;
  created_at: string;
};

export type AdminSupportTicket = {
  id: string;
  user_id: string;
  telegram_id: number;
  username: string | null;
  display_name: string | null;
  subject: string;
  message: string;
  status: string;
  created_at: string;
  closed_at: string | null;
};

export async function createSupportTicket(
  subject: string,
  message: string,
  fetchImpl: typeof fetch = fetch,
): Promise<SupportTicket> {
  return requestJson<SupportTicket>(
    "/api/v1/support",
    {
      method: "POST",
      body: JSON.stringify({ subject, message }),
    },
    fetchImpl,
  );
}

export async function getAdminSupportTickets(
  fetchImpl: typeof fetch = fetch,
): Promise<AdminSupportTicket[]> {
  return requestJson<AdminSupportTicket[]>("/api/v1/admin/support", { method: "GET" }, fetchImpl);
}

export async function closeAdminSupportTicket(
  ticketId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<{ id: string; status: string }> {
  return requestJson<{ id: string; status: string }>(
    `/api/v1/admin/support/${ticketId}/close`,
    { method: "POST" },
    fetchImpl,
  );
}

export type AdminOverview = {
  start: string;
  end: string;
  active_users: number;
  open_accounts: number;
  payments: number;
  stars: number;
  refunds: number;
  sources: { source: string; count: number }[];
  models: {
    model: string;
    calls: number;
    prompt_tokens: number;
    completion_tokens: number;
    errors: number;
    latency_p50_ms: number | null;
  }[];
  cache: {
    l1_hits: number;
    l1_misses: number;
    l2_hits: number;
    process_generations: number;
    rows_in_range: number;
    hits_in_range: number;
  };
  feedback: { forecast_type: string; prompt_version: string; count: number }[];
  definitions: Record<string, string>;
};

export async function getAdminOverview(
  start: string,
  end: string,
  fetchImpl: typeof fetch = fetch,
): Promise<AdminOverview> {
  const params = new URLSearchParams();
  if (start) {
    params.set("start", start);
  }
  if (end) {
    params.set("end", end);
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return requestJson<AdminOverview>(`/api/v1/admin/overview${suffix}`, { method: "GET" }, fetchImpl);
}

export type AdminUser = {
  user_id: string;
  telegram_id: number;
  username: string | null;
  display_name: string | null;
  premium: boolean;
};

export type AdminUserPage = {
  users: AdminUser[];
  total: number;
  page: number;
  pageSize: number;
};

export async function getAdminUsers(
  page: number,
  fetchImpl: typeof fetch = fetch,
  pageSize = 10,
): Promise<AdminUserPage> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  const body = await requestJson<{
    users: AdminUser[];
    total: number;
    page: number;
    page_size: number;
  }>(`/api/v1/admin/users?${params.toString()}`, { method: "GET" }, fetchImpl);
  return {
    users: body.users,
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  };
}

export async function grantAdminPeriod(
  userId: string,
  days: number,
  reason: string,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  await requestJson<unknown>(
    "/api/v1/billing/admin-grants",
    {
      method: "POST",
      body: JSON.stringify({ user_id: userId, days, reason, confirm: true }),
    },
    fetchImpl,
  );
}

export async function refundCharge(
  chargeId: string,
  reason: string,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  await requestJson<unknown>(
    "/api/v1/billing/refunds",
    {
      method: "POST",
      body: JSON.stringify({
        telegram_payment_charge_id: chargeId,
        reason,
        confirm: true,
      }),
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

export type TopupResponse = {
  order_id: string;
  invoice_link: string;
  balance: number;
  amount: number;
};

export type SpendResponse = {
  balance: number;
  allowed: boolean;
  charged: boolean;
  price: number;
};

export async function createTopup(
  amount: number,
  idempotencyKey: string,
  fetchImpl: typeof fetch = fetch,
): Promise<TopupResponse> {
  return requestJson<TopupResponse>(
    "/api/v1/stars/topups",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ amount }),
    },
    fetchImpl,
  );
}

export async function buyPremium(
  idempotencyKey: string,
  fetchImpl: typeof fetch = fetch,
): Promise<{ balance: number; charged: boolean }> {
  return requestJson<{ balance: number; charged: boolean }>(
    "/api/v1/stars/premium",
    { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
    fetchImpl,
  );
}

export async function redeemBalanceCode(
  code: string,
  fetchImpl: typeof fetch = fetch,
): Promise<{ balance: number }> {
  return requestJson<{ balance: number }>(
    "/api/v1/stars/codes",
    { method: "POST", body: JSON.stringify({ code }) },
    fetchImpl,
  );
}

export async function createBalanceCode(
  code: string,
  stars: number,
  uses: number,
  days: number,
  fetchImpl: typeof fetch = fetch,
): Promise<{ code: string }> {
  return requestJson<{ code: string }>(
    "/api/v1/admin/balance-codes",
    { method: "POST", body: JSON.stringify({ code, stars, uses, days }) },
    fetchImpl,
  );
}

export async function queueBroadcast(
  body: string,
  audience: string,
  fetchImpl: typeof fetch = fetch,
): Promise<{ id: string; status: string }> {
  return requestJson<{ id: string; status: string }>(
    "/api/v1/admin/broadcasts",
    { method: "POST", body: JSON.stringify({ body, audience }) },
    fetchImpl,
  );
}

export async function spendStars(
  body:
    | { feature: "natal" }
    | { feature: "compatibility"; left_sign: string; right_sign: string }
    | { feature: "favorable"; month: string; event: string; custom: string }
    | { feature: "affirmation"; category: string },
  fetchImpl: typeof fetch = fetch,
): Promise<SpendResponse> {
  return requestJson<SpendResponse>(
    "/api/v1/stars/spends",
    { method: "POST", body: JSON.stringify(body) },
    fetchImpl,
  );
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

export type AssistantMessage = {
  id: string;
  role: string;
  content: string;
  created_at: string;
};

export type AssistantReply = {
  status: string;
  reply: string | null;
  remaining: number | null;
  replayed: boolean;
  code: string | null;
};

export type AssistantHistory = {
  messages: AssistantMessage[];
  remaining: number | null;
};

export async function getAssistantMessages(
  fetchImpl: typeof fetch = fetch,
  before?: string,
): Promise<AssistantHistory> {
  const suffix = before === undefined ? "" : `?before=${encodeURIComponent(before)}`;
  return requestJson<AssistantHistory>(
    `/api/v1/assistant/messages${suffix}`,
    { method: "GET" },
    fetchImpl,
  );
}

export async function askAssistant(
  text: string,
  idempotencyKey: string,
  fetchImpl: typeof fetch = fetch,
): Promise<AssistantReply> {
  return requestJson<AssistantReply>(
    "/api/v1/assistant/messages",
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ text }),
    },
    fetchImpl,
  );
}

export function readingKey(): string {
  const stamp = Date.now().toString(36);
  const salt = Math.random().toString(36).slice(2, 12);
  return `read${stamp}${salt}`;
}

function readingPath(kind: string, query: ReadingQuery): string {
  const params = new URLSearchParams();
  if (query.topic) {
    params.set("topic", query.topic);
  }
  if (query.month) {
    params.set("month", query.month);
  }
  if (query.relatedId) {
    params.set("related_id", query.relatedId);
  }
  if (query.leftSign) {
    params.set("left_sign", query.leftSign);
  }
  if (query.rightSign) {
    params.set("right_sign", query.rightSign);
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return `/api/v1/readings/${kind}${suffix}`;
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
