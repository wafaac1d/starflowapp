import { useEffect, useState } from "react";

import { BackHome, BottomSheet, Button } from "../components/ui/controls";
import { text, type TextKey } from "../resources";
import { applyTheme, readThemeChoice, type ThemeChoice } from "../theme";
import { readWebApp } from "../telegram";

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

const THEMES: { id: ThemeChoice; label: TextKey }[] = [
  { id: "light", label: "ui.theme.light" },
  { id: "dark", label: "ui.theme.dark" },
  { id: "telegram", label: "ui.theme.telegram" },
];

export function SettingsPage() {
  const [open, setOpen] = useState(false);
  const [choice, setChoice] = useState<ThemeChoice>(readThemeChoice());
  return (
    <main className="shell">
      <h1>{text("ui.settings.title")}</h1>
      <p className="lead">{text("bot.settings")}</p>
      <p>{text(THEMES.find((item) => item.id === choice)?.label ?? "ui.theme.light")}</p>
      <Button
        tone="outline"
        label={text("ui.theme.open")}
        onClick={() => {
          setOpen(true);
        }}
      />
      <BottomSheet
        open={open}
        title={text("ui.theme.title")}
        onClose={() => {
          setOpen(false);
        }}
      >
        <div className="stack">
          {THEMES.map((item) => (
            <Button
              key={item.id}
              {...(item.id === choice ? {} : { tone: "outline" as const })}
              label={text(item.label)}
              onClick={() => {
                applyTheme(item.id);
                setChoice(item.id);
                setOpen(false);
              }}
            />
          ))}
        </div>
      </BottomSheet>
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
