import { useState } from "react";
import { useNavigate } from "react-router";

import { STAR_SILENCE, useReading } from "../readingWait";
import { AlertDialog } from "../shared/ui/AlertDialog/AlertDialog";
import { TopUpDialog } from "./TopUpDialog";

const LOCKED = "Эта функция только с Premium.";

const TOPICS: Record<string, string> = {
  love: "отношения",
  relations: "отношения",
  work: "работа",
  finance: "финансы",
  health: "эмоциональное состояние",
  state: "эмоциональное состояние",
};

const PAIR = new Set(["dialog", "emotions", "values"]);

export type PairSigns = {
  leftSign: string;
  rightSign: string;
};

export function useTopicDetail(premium: boolean, pair?: PairSigns) {
  const navigate = useNavigate();
  const [locked, setLocked] = useState(false);
  const [topUp, setTopUp] = useState(false);
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState<string | null>(null);
  const query =
    topic === null
      ? {}
      : pair === undefined
        ? { topic }
        : { topic, leftSign: pair.leftSign, rightSign: pair.rightSign };
  const reading = useReading(pair === undefined ? "topics" : "synastry", query, topic !== null);
  const open = (id: string, label: string) => {
    if (pair !== undefined) {
      if (!PAIR.has(id)) {
        return;
      }
      if (pair.leftSign === "" || pair.rightSign === "") {
        return;
      }
      setTitle(label);
      setTopic(id);
      return;
    }
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
  const starsReply = reading.face.phase === "stars";
  const starsBody = reading.face.phase === "stars" ? reading.face.body : "";
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
              : reading.face.phase === "stars"
                ? starsBody
                : STAR_SILENCE
      }
      busy={reading.face.phase === "loading"}
      dismissLabel="Закрыть"
      onDismiss={close}
      {...(starsReply
        ? {
            actionLabel: "Пополнить",
            onAction: () => {
              setTopUp(true);
            },
          }
        : premiumReply
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
  return {
    open,
    dialog: (
      <>
        {dialog}
        {topUp ? <TopUpDialog balance={null} onClose={() => setTopUp(false)} /> : null}
      </>
    ),
  };
}
