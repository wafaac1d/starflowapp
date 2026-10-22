import { useQuery } from "@tanstack/react-query";

import { getRetro } from "../api/client";
import { BackHome } from "../components/ui/controls";
import { text } from "../resources";

type RetroPageProps = {
  fetchImpl?: typeof fetch;
};

export function RetroPage({ fetchImpl = fetch }: RetroPageProps) {
  const stations = useQuery({
    queryKey: ["retro"],
    queryFn: () => getRetro(fetchImpl),
  });
  return (
    <main className="shell">
      <h1>{text("ui.retro.title")}</h1>
      <p className="lead">{text("ui.retro.lead")}</p>
      <ul>
        {(stations.data ?? []).map((item) => (
          <li key={`${item.planet}-${item.local_date}`}>
            {item.planet} {item.local_date}
          </li>
        ))}
      </ul>
      <BackHome />
    </main>
  );
}
