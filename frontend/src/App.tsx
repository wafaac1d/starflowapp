import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { BrowserRouter, Route, Routes, useParams } from "react-router";

import { openSession } from "./api/client";
import { ErrorState, LoadingScreen } from "./components/ui/controls";
import { EdgeSwipe } from "./components/ui/EdgeSwipe";
import { HelpPage, PaySupportPage, PremiumPage, SettingsPage, TermsPage } from "./pages/InfoPages";
import { AdminPage } from "./pages/AdminPage";
import { DeletePage } from "./pages/DeletePage";
import { RetroPage } from "./pages/RetroPage";
import { FavoritesPage, HistoryPage, ReferralPage, RelatedPage } from "./pages/LibraryPages";
import { CalendarPage, MonthPage } from "./pages/CalendarPage";
import { ChartPage } from "./pages/ChartPage";
import { AssistantPage } from "./pages/AssistantPage";
import { BottomNavigation } from "./components/ui/editorial";
import { HomePage } from "./pages/HomePage";
import { ReadingPage } from "./pages/ReadingPage";
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

function ReadingRoute() {
  const params = useParams();
  return <ReadingPage kind={params.kind ?? "day"} />;
}

function AuthedApp({ initData }: { initData: string }) {
  const session = useQuery({
    queryKey: ["session"],
    queryFn: () => openSession(initData),
    retry: false,
  });
  if (session.isPending) {
    return <LoadingScreen />;
  }
  if (session.isError || session.data === undefined) {
    return (
      <main className="shell">
        <ErrorState
          message={text("ui.common.error")}
          onRetry={() => {
            void session.refetch();
          }}
        />
      </main>
    );
  }
  const profile = session.data;
  const ready = profile.step === "done";
  return (
    <div className={ready ? "app-nav" : undefined}>
      <EdgeSwipe />
      <Routes>
      <Route
        path="/"
        element={
          profile.step === "done" ? <HomePage profile={profile} /> : <OnboardingPage profile={profile} />
        }
      />
      <Route path="/calendar" element={<CalendarPage />} />
      <Route path="/calendar/month" element={<MonthPage />} />
      <Route path="/chart" element={<ChartPage />} />
      <Route path="/reading/:kind" element={<ReadingRoute />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="/favorites" element={<FavoritesPage />} />
      <Route path="/related" element={<RelatedPage />} />
      <Route path="/referral" element={<ReferralPage />} />
      <Route path="/profile" element={<ProfilePage profile={profile} />} />
      <Route path="/assistant" element={<AssistantPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/delete" element={<DeletePage />} />
      <Route path="/retro" element={<RetroPage />} />
      <Route path="/admin" element={<AdminPage isAdmin={profile.is_admin} />} />
      <Route path="/premium" element={<PremiumPage profile={profile} />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/help" element={<HelpPage />} />
      <Route path="/paysupport" element={<PaySupportPage />} />
      <Route path="*" element={<OpenAppPage />} />
    </Routes>
      {ready ? <BottomNavigation /> : null}
    </div>
  );
}
