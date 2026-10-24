import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { getReading, readingKey, startReading } from "../api/client";
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
  const reading = useMutation({
    mutationFn: async (topic: string) => {
      const started = await startReading("topics", readingKey(), fetch, { topic });
      if (started.status === "ready" || started.status === "fallback" || started.body) {
        return started;
      }
      return getReading("topics", fetch, { topic });
    },
  });
  const open = (id: string, label: string) => {
    const topic = TOPICS[id];
    if (topic === undefined) {
      return;
    }
    if (!premium) {
      setLocked(true);
      return;
    }
    setTitle(label);
    reading.mutate(topic);
  };
  const close = () => {
    setLocked(false);
    setTitle("");
    reading.reset();
  };
  const premiumReply = reading.data?.status === "premium";
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
      title={reading.data?.title || title}
      body={
        reading.isPending
          ? "Готовим текст."
          : premiumReply
            ? LOCKED
            : reading.data?.body || "Не удалось получить текст."
      }
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
