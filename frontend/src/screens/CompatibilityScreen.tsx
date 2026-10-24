import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";

import { getRelated, type ProfileResponse } from "../api/client";
import { compatRows, getCompatRows, ownerFixture, partnerFixture, peopleFixture } from "../api/fixtures";
import { queryKeys } from "../api/keys";
import { Avatar } from "../shared/ui/Avatar/Avatar";
import { ListRow } from "../shared/ui/ListRow/ListRow";
import { Screen } from "../shared/ui/Screen/Screen";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import { initialsOf } from "./format";
import styles from "./screens.module.css";

export function CompatibilityScreen({ profile }: { profile: ProfileResponse }) {
  const params = useParams();
  const personId = params.personId ?? partnerFixture.id;
  const related = useQuery({ queryKey: queryKeys.related, queryFn: () => getRelated() });
  const rows = useQuery({ queryKey: queryKeys.compatibility(personId), queryFn: getCompatRows });
  const known = peopleFixture.find((person) => person.id === personId);
  const fromApi = related.data?.find((person) => person.related_id === personId);
  const partner = known ?? {
    id: personId,
    initials: initialsOf(fromApi?.display_name ?? partnerFixture.name),
    name: fromApi?.display_name ?? partnerFixture.name,
    birthDate: fromApi?.birth_date ?? partnerFixture.birthDate,
    sign: partnerFixture.sign,
  };
  const owner = {
    initials: initialsOf(profile.display_name ?? ownerFixture.name).slice(0, 1) || ownerFixture.initials,
    name: profile.display_name ?? ownerFixture.name,
    birthDate: profile.birth_date ?? ownerFixture.birthDate,
    sign: profile.calendar_sign ?? ownerFixture.sign,
  };
  return (
    <Screen tab="today">
      <TopBar title="Совместимость" back />
      <div className={styles.pair}>
        <article className={styles.person}>
          <Avatar letters={owner.initials} />
          <strong>{owner.name}</strong>
          <p>{owner.birthDate}</p>
          <p>{owner.sign}</p>
        </article>
        <article className={styles.person}>
          <Avatar letters={partner.initials} />
          <strong>{partner.name}</strong>
          <p>{partner.birthDate}</p>
          <p>{partner.sign}</p>
        </article>
      </div>
      <img className={styles.wheel} src="/illustrations/png/compatibility_diagram.png" alt="" />
      <div className={styles.stack}>
        {(rows.data ?? compatRows).map((row) => (
          <ListRow key={row.id} icon={row.icon} title={row.title} subtitle={row.subtitle} />
        ))}
      </div>
    </Screen>
  );
}
