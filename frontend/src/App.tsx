import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import { openSession } from "./api/client";
import { queryKeys } from "./api/keys";
import { ErrorState } from "./shared/ui/ErrorState/ErrorState";
import { Skeleton } from "./shared/ui/Skeleton/Skeleton";
import { AdminPage } from "./pages/AdminPage";
import { DeletePage } from "./pages/DeletePage";
import { RetroPage } from "./pages/RetroPage";
import { FavoritesPage, HistoryPage, ReferralPage } from "./pages/LibraryPages";
import { HelpPage, PaySupportPage, TermsPage } from "./pages/InfoPages";
import { OpenAppPage } from "./pages/OpenAppPage";
import { BirthScreen } from "./screens/BirthScreen";
import { CalendarScreen } from "./screens/CalendarScreen";
import { ChatScreen } from "./screens/ChatScreen";
import { CompatibilityScreen } from "./screens/CompatibilityScreen";
import { ForecastScreen } from "./screens/ForecastScreen";
import { NatalScreen } from "./screens/NatalScreen";
import { PeopleScreen } from "./screens/PeopleScreen";
import { PremiumScreen } from "./screens/PremiumScreen";
import { ProfileScreen } from "./screens/ProfileScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { TodayScreen } from "./screens/TodayScreen";
import { WelcomeScreen } from "./screens/WelcomeScreen";
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
        <div className="app-column">
          <AuthedApp initData={webApp.initData} />
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function AuthedApp({ initData }: { initData: string }) {
  const session = useQuery({
    queryKey: queryKeys.session,
    queryFn: () => openSession(initData),
    retry: false,
  });
  if (session.isPending) {
    return <Skeleton lines={4} />;
  }
  if (session.isError || session.data === undefined) {
    return (
      <ErrorState
        message="Не удалось открыть сессию"
        onRetry={() => {
          void session.refetch();
        }}
      />
    );
  }
  const profile = session.data;
  const ready = profile.step === "done";
  const displayName = profile.display_name ?? nameFromInitData(initData);
  return (
    <Routes>
      <Route path="/welcome" element={<WelcomeScreen />} />
      <Route
        path="/onboarding/birth"
        element={<BirthScreen profile={profile} displayName={displayName} />}
      />
      <Route path="/" element={ready ? <TodayScreen profile={profile} /> : <WelcomeScreen />} />
      <Route path="/forecast" element={<ForecastScreen premium={profile.is_premium} />} />
      <Route path="/calendar" element={<CalendarScreen />} />
      <Route path="/natal" element={<NatalScreen />} />
      <Route path="/compatibility" element={<CompatibilityScreen profile={profile} />} />
      <Route path="/compatibility/:personId" element={<CompatibilityScreen profile={profile} />} />
      <Route path="/chat" element={<ChatScreen />} />
      <Route path="/people" element={<PeopleScreen />} />
      <Route path="/profile" element={<ProfileScreen profile={profile} />} />
      <Route path="/settings" element={<SettingsScreen />} />
      <Route path="/premium" element={<PremiumScreen />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="/favorites" element={<FavoritesPage />} />
      <Route path="/referral" element={<ReferralPage />} />
      <Route path="/delete" element={<DeletePage />} />
      <Route path="/retro" element={<RetroPage />} />
      <Route path="/admin" element={<AdminPage isAdmin={profile.is_admin} />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/help" element={<HelpPage />} />
      <Route path="/paysupport" element={<PaySupportPage />} />
      <Route path="/chart" element={<Navigate to="/natal" replace />} />
      <Route path="/assistant" element={<Navigate to="/chat" replace />} />
      <Route path="/related" element={<Navigate to="/people" replace />} />
      <Route path="/reading/:kind" element={<Navigate to="/forecast" replace />} />
      <Route path="*" element={<OpenAppPage />} />
    </Routes>
  );
}

function nameFromInitData(initData: string): string {
  const raw = new URLSearchParams(initData).get("user");
  if (raw === null) {
    return "";
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (isRecord(parsed) && typeof parsed.first_name === "string") {
      return parsed.first_name;
    }
  } catch {
    return "";
  }
  return "";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
