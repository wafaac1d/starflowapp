import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router";

import { openSession } from "./api/client";
import { Button } from "./components/ui/controls";
import { HelpPage, PaySupportPage, PremiumPage, SettingsPage, TermsPage } from "./pages/InfoPages";
import { ChartPage } from "./pages/ChartPage";
import { HomePage } from "./pages/HomePage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { OpenAppPage } from "./pages/OpenAppPage";
import { ProfilePage } from "./pages/ProfilePage";
import { text } from "./resources";
import { readWebApp } from "./telegram";

export function App() {
  const webApp = useMemo(() => readWebApp(), []);
  const [client] = useState(() => new QueryClient());
  if (webApp === null) {
    return <OpenAppPage />;
  }
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <AuthedApp initData={webApp.initData} />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function AuthedApp({ initData }: { initData: string }) {
  const session = useQuery({
    queryKey: ["session"],
    queryFn: () => openSession(initData),
    retry: false,
  });
  if (session.isPending) {
    return (
      <main className="shell">
        <p className="lead">{text("ui.common.loading")}</p>
      </main>
    );
  }
  if (session.isError || session.data === undefined) {
    return (
      <main className="shell">
        <p role="alert">{text("ui.common.error")}</p>
        <Button
          label={text("ui.common.retry")}
          onClick={() => {
            void session.refetch();
          }}
        />
      </main>
    );
  }
  const profile = session.data;
  return (
    <Routes>
      <Route
        path="/"
        element={
          profile.step === "done" ? <HomePage profile={profile} /> : <OnboardingPage profile={profile} />
        }
      />
      <Route path="/chart" element={<ChartPage />} />
      <Route path="/profile" element={<ProfilePage profile={profile} />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/premium" element={<PremiumPage profile={profile} />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/help" element={<HelpPage />} />
      <Route path="/paysupport" element={<PaySupportPage />} />
      <Route path="*" element={<OpenAppPage />} />
    </Routes>
  );
}
