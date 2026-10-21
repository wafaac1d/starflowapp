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
