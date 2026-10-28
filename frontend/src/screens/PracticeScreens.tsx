import { useNavigate } from "react-router";

import { Screen } from "../shared/ui/Screen/Screen";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

function PracticePage({ title, lead, image }: { title: string; lead: string; image: string }) {
  const navigate = useNavigate();
  return (
    <Screen>
      <TopBar
        title={title}
        back
        onBack={() => {
          void navigate("/");
        }}
      />
      <img className={styles.practiceHero} src={image} alt="" />
      <p className={styles.paragraph}>{lead}</p>
    </Screen>
  );
}

export function AffirmationsScreen() {
  return (
    <PracticePage
      title="Аффирмации"
      lead="Настройтесь на свой ритм"
      image="/affirmations/affirmations_256.png"
    />
  );
}

export function FavorableDateScreen() {
  return (
    <PracticePage
      title="Благоприятная дата"
      lead="Подберите день для события"
      image="/favorable_date/favorable_date_256.png"
    />
  );
}
