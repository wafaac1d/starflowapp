import type { QueryClient } from "@tanstack/react-query";

import type { ProfileResponse } from "./api/client";
import { queryKeys } from "./api/keys";

export function writeStarBalance(client: QueryClient, balance: number): void {
  client.setQueryData<ProfileResponse>(queryKeys.session, (current) => {
    if (current === undefined) {
      return current;
    }
    return { ...current, star_balance: balance };
  });
}

export function holdStarBalance(client: QueryClient, price: number): () => void {
  const current = client.getQueryData<ProfileResponse>(queryKeys.session);
  if (current === undefined) {
    return () => undefined;
  }
  const previous = current.star_balance;
  writeStarBalance(client, Math.max(0, previous - price));
  return () => {
    writeStarBalance(client, previous);
  };
}
