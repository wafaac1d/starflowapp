import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { getMeta, type ProfileResponse } from "../api/client";
import { Button, LogoSlot } from "../components/ui/controls";
import { logoAvailable } from "../generated/logo";
import { formatText, homeCopy, pluralText, text } from "../resources";

type HomePageProps = {
  profile: ProfileResponse;
};

export function HomePage({ profile }: HomePageProps) {
  const meta = useQuery({
    queryKey: ["meta"],
    queryFn: () => getMeta(),
    enabled: false,
    retry: false,
  });
  const status = meta.isSuccess
    ? `${homeCopy.status_ready}. ${homeCopy.price_label}: ${meta.data.premium_price_stars}`
    : meta.isError
      ? homeCopy.status_failed
      : homeCopy.lead;
  const sign =
    profile.calendar_sign === null
      ? text("ui.onboarding.sign_title")
      : profile.display_name
        ? formatText("ui.onboarding.sign_named", { name: profile.display_name })
        : text("ui.onboarding.sign_title");

  return (
    <main className="shell">
      <section className="surface">
        <LogoSlot available={logoAvailable} src="/logo.png" label={homeCopy.logo_label} />
        <h1>{sign}</h1>
        {profile.calendar_sign !== null ? <p className="lead">{profile.calendar_sign}</p> : null}
        <p className="lead">{status}</p>
        <p className="disclaimer">{homeCopy.disclaimer}</p>
        <Button
          label={homeCopy.action}
          loading={meta.isFetching}
          onClick={() => {
            void meta.refetch();
          }}
        />
        <nav className="link-row">
          <Link to="/chart">{text("ui.chart.title")}</Link>
          <Link to="/profile">{text("ui.profile.title")}</Link>
          <Link to="/settings">{text("ui.settings.title")}</Link>
          <Link to="/premium">{text("ui.premium.title")}</Link>
          <Link to="/terms">{text("ui.terms.title")}</Link>
          <Link to="/help">{text("ui.help.title")}</Link>
          <Link to="/paysupport">{text("ui.paysupport.title")}</Link>
        </nav>
        {meta.isSuccess ? (
          <p className="meta">{pluralText("ui.premium.questions", meta.data.assistant_questions)}</p>
        ) : null}
      </section>
    </main>
  );
}
