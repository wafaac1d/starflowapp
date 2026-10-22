import { useEffect } from "react";

import { BackHome } from "../components/ui/controls";
import { text, type TextKey } from "../resources";
import { readWebApp } from "../telegram";

export { SettingsPage } from "./SettingsPage";

export { PremiumPage } from "./PremiumPage";

type ScreenProps = {
  title: TextKey;
  body: string;
};

export function TextScreen({ title, body }: ScreenProps) {
  useScreenBack();
  return (
    <main className="shell">
      <h1>{text(title)}</h1>
      <p className="lead">{body}</p>
      <BackHome />
    </main>
  );
}

export function TermsPage() {
  return <TextScreen title="ui.terms.title" body={text("bot.terms")} />;
}

export function HelpPage() {
  return <TextScreen title="ui.help.title" body={text("bot.help")} />;
}

export function PaySupportPage() {
  return <TextScreen title="ui.paysupport.title" body={text("bot.paysupport")} />;
}

function useScreenBack(): void {
  useEffect(() => {
    const webApp = readWebApp();
    if (webApp === null) {
      return;
    }
    webApp.showBack(() => {
      window.history.back();
    });
    return () => {
      webApp.hideBack();
    };
  }, []);
}
