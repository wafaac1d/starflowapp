import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import type { ProfileResponse } from "../api/client";
import { getProfileTrait } from "../api/fixtures";
import { queryKeys } from "../api/keys";
import { titled } from "../case";
import { Avatar } from "../shared/ui/Avatar/Avatar";
import { Icon } from "../shared/ui/Icon/Icon";
import { ListRow } from "../shared/ui/ListRow/ListRow";
import { Screen } from "../shared/ui/Screen/Screen";
import styles from "./screens.module.css";

export function ProfileScreen({ profile }: { profile: ProfileResponse }) {
  const navigate = useNavigate();
  const trait = useQuery({ queryKey: queryKeys.profileTrait, queryFn: getProfileTrait });
  const sign = profile.calendar_sign === null ? "" : titled(profile.calendar_sign);
  const born = profile.birth_date ?? "";
  return (
    <Screen tab="profile">
      <div className={styles.fill}>
      <div className={styles.topRow}>
        <span />
        <button
          type="button"
          className={styles.profileButton}
          aria-label="Настройки"
          onClick={() => {
            void navigate("/settings");
          }}
        >
          <Icon name="gear" size={22} />
        </button>
      </div>
      <div className={styles.identity}>
        <button
          type="button"
          className={styles.avatarButton}
          aria-label="Редактировать профиль"
          onClick={() => {
            void navigate("/onboarding/birth");
          }}
        >
          <Avatar letters={profile.display_name?.slice(0, 1) ?? ""} size="l" />
        </button>
        <span className={styles.identityText}>
          <h1 className={styles.name}>{profile.display_name}</h1>
          <p className={styles.meta}>
            {sign} · {born}
          </p>
        </span>
      </div>
      <article className={`${styles.decision} ${styles.trait}`}>
        <span className={styles.decisionHead}>
          <Icon name="profile_trait_sparkle" size={22} />
          <span>{trait.data ?? ""}</span>
        </span>
      </article>
      <div>
        <ListRow plain title="Данные рождения" chevron to="/onboarding/birth" />
        <ListRow
          plain
          title="Добавить близкого"
          chevron
          onClick={() => {
            void navigate("/people", { state: { add: true } });
          }}
        />
        <ListRow plain title="Избранное" chevron to="/favorites" />
        <ListRow plain title="Моя подписка" chevron to="/premium" />
        {profile.is_admin ? <ListRow plain title="Админ" chevron to="/admin" /> : null}
      </div>
      <div className={styles.deleteRow}>
        <ListRow plain title="Удалить данные" to="/delete" />
      </div>
      </div>
    </Screen>
  );
}
