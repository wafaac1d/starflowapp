import { useState } from "react";
import { useNavigate } from "react-router";

import { STAR_SILENCE, useReading } from "../readingWait";
import { AlertDialog } from "../shared/ui/AlertDialog/AlertDialog";

const LOCKED = "Эта функция только с Premium.";

const TOPICS: Record<string, string> = {
  love: "отношения",
  relations: "отношения",
  dialog: "отношения",
  values: "отношения",
  work: "работа",
  finance: "финансы",
  health: "эмоциональное состояние",
  state: "эмоциональное состояние",
  emotions: "эмоциональное состояние",
};

export function useTopicDetail(premium: boolean) {
  const navigate = useNavigate();
  const [locked, setLocked] = useState(false);
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState<string | null>(null);
  const reading = useReading("topics", topic === null ? {} : { topic }, topic !== null);
  const open = (id: string, label: string) => {
    const next = TOPICS[id];
    if (next === undefined) {
      return;
    }
    if (!premium) {
      setLocked(true);
      return;
    }
    setTitle(label);
    setTopic(next);
  };
  const close = () => {
    setLocked(false);
    setTitle("");
    setTopic(null);
  };
  const premiumReply = reading.face.phase === "premium";
  const dialog = locked ? (
    <AlertDialog
      title={LOCKED}
      body="Разбор темы открывается на оплаченном периоде."
      dismissLabel="Понятно"
      onDismiss={close}
      actionLabel="Подключить"
      onAction={() => {
        close();
        void navigate("/premium");
      }}
    />
  ) : title !== "" ? (
    <AlertDialog
      title={reading.face.phase === "ready" && reading.face.title !== "" ? reading.face.title : title}
      body={
        reading.face.phase === "ready"
          ? reading.face.body
          : reading.face.phase === "blocked"
            ? reading.face.body
            : reading.face.phase === "premium"
              ? "Разбор темы открывается на оплаченном периоде."
              : STAR_SILENCE
      }
      busy={reading.face.phase === "loading"}
      dismissLabel="Закрыть"
      onDismiss={close}
      {...(premiumReply
        ? {
            actionLabel: "Подключить",
            onAction: () => {
              close();
              void navigate("/premium");
            },
          }
        : {})}
    />
  ) : null;
  return { open, dialog };
}
