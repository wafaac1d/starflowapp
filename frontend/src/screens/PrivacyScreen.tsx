import { privacyPolicy } from "../privacyPolicy";
import { Screen } from "../shared/ui/Screen/Screen";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

export function PrivacyScreen() {
  return (
    <Screen>
      <TopBar title={privacyPolicy.title} align="left" back />
      <p className={styles.meta}>{privacyPolicy.updated}</p>
      <div className={styles.policy}>
        {privacyPolicy.sections.map((section) => (
          <section key={section.title}>
            <h2>{section.title}</h2>
            {section.paragraphs.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </section>
        ))}
      </div>
    </Screen>
  );
}
