import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router";

import { getFavoriteReading, getFavorites } from "../api/client";
import { queryKeys } from "../api/keys";
import { text } from "../resources";
import { ErrorState } from "../shared/ui/ErrorState/ErrorState";
import { ListRow } from "../shared/ui/ListRow/ListRow";
import { Screen } from "../shared/ui/Screen/Screen";
import { Skeleton } from "../shared/ui/Skeleton/Skeleton";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

type FavoritesScreenProps = {
  fetchImpl?: typeof fetch;
};

export function FavoritesScreen({ fetchImpl = fetch }: FavoritesScreenProps) {
  const favorites = useQuery({
    queryKey: queryKeys.favorites,
    queryFn: () => getFavorites(fetchImpl),
  });
  const rows = favorites.data ?? [];
  return (
    <Screen tab="profile">
      <TopBar title={text("ui.reading.favorites")} back />
      {favorites.isPending ? <Skeleton lines={3} /> : null}
      {favorites.isError ? (
        <ErrorState
          message="Не удалось открыть избранное"
          onRetry={() => {
            void favorites.refetch();
          }}
        />
      ) : null}
      {favorites.isSuccess && rows.length === 0 ? <p className={styles.lead}>{text("ui.empty.favorites")}</p> : null}
      {rows.length > 0 ? (
        <div className={styles.stack}>
          {rows.map((item) => (
            <ListRow
              key={item.history_id}
              icon="save_bookmark"
              title={item.title}
              chevron
              to={`/favorites/${item.history_id}`}
            />
          ))}
        </div>
      ) : null}
    </Screen>
  );
}

export function SavedFavoriteScreen({ fetchImpl = fetch }: FavoritesScreenProps) {
  const navigate = useNavigate();
  const params = useParams();
  const historyId = params.historyId ?? "";
  const reading = useQuery({
    queryKey: [...queryKeys.favorites, historyId],
    queryFn: () => getFavoriteReading(historyId, fetchImpl),
    enabled: historyId !== "",
  });
  const title = reading.data?.title ?? text("ui.reading.favorites");
  return (
    <Screen tab="profile">
      <TopBar
        title={title}
        align="left"
        back
        onBack={() => {
          void navigate("/favorites");
        }}
      />
      {reading.isPending ? <Skeleton lines={4} /> : null}
      {reading.isError ? (
        <ErrorState
          message="Не удалось открыть прогноз"
          onRetry={() => {
            void reading.refetch();
          }}
        />
      ) : null}
      {reading.data !== undefined ? <p className={styles.paragraph}>{reading.data.body}</p> : null}
    </Screen>
  );
}
