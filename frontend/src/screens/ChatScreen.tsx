import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  askAssistant,
  getAssistantMessages,
  readingKey,
  type AssistantMessage,
  type AssistantReply,
} from "../api/client";
import { queryKeys } from "../api/keys";
import { STAR_SILENCE } from "../readingWait";
import { ChatBubble } from "../shared/ui/ChatBubble/ChatBubble";
import { ChatInput } from "../shared/ui/ChatInput/ChatInput";
import { Chip } from "../shared/ui/Chip/Chip";
import { Screen } from "../shared/ui/Screen/Screen";
import { StarPrice } from "../shared/ui/StarPrice/StarPrice";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import { holdStarBalance } from "../starBalance";
import { QUESTION_STARS } from "../stars";
import styles from "./screens.module.css";
import { TopUpDialog } from "./TopUpDialog";

const STORED = new Set(["ready", "off_topic", "injection"]);

type Outgoing = {
  text: string;
  at: string;
  knownIds: string[];
};

export function ChatScreen({ premium, balance = 0 }: { premium: boolean; balance?: number }) {
  const client = useQueryClient();
  const [draft, setDraft] = useState("");
  const [topUp, setTopUp] = useState(false);
  const [live, setLive] = useState<Outgoing | null>(null);
  const history = useQuery({ queryKey: queryKeys.assistant, queryFn: () => getAssistantMessages() });
  const ask = useMutation({
    mutationFn: (outgoing: Outgoing) => askAssistant(outgoing.text, readingKey()),
    onMutate: () => (premium ? undefined : holdStarBalance(client, QUESTION_STARS)),
    onSuccess: (result, _outgoing, restore) => {
      if (!premium && result.status !== "ready") {
        restore?.();
      }
      if (!premium && result.status === "ready") {
        void client.invalidateQueries({ queryKey: queryKeys.session });
      }
      if (!STORED.has(result.status) || result.reply == null || result.reply === "") {
        return;
      }
      void client.invalidateQueries({ queryKey: queryKeys.assistant, exact: true });
    },
    onError: (_error, _outgoing, restore) => {
      restore?.();
    },
  });
  const messages = history.data?.messages ?? [];
  const known = new Set(live?.knownIds ?? []);
  const question = live?.text ?? "";
  const answer = ask.isPending ? "" : assistantLine(ask.data, ask.isError);
  const showUser = live !== null && !alreadyStored(messages, known, "user", question);
  const showAssistant = live !== null && !alreadyStored(messages, known, "assistant", answer);
  const remaining = ask.data?.remaining ?? history.data?.remaining;
  const empty = history.isSuccess && messages.length === 0 && live === null;
  const priced = !premium;
  const short = priced && balance < QUESTION_STARS;
  const tail = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ask.data?.status === "stars") {
      setTopUp(true);
    }
  }, [ask.data]);
  useEffect(() => {
    const node = tail.current;
    if (node !== null && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ block: "end" });
    }
  }, [messages.length, question, answer, ask.isPending]);
  return (
    <Screen tab="chat" fit>
      <div className={styles.chatFill}>
        <TopBar title="Астропомощник" back />
        <div
          className={empty ? styles.chatEmptyStage : styles.chatLog}
          {...(empty ? {} : { role: "log" as const, "aria-label": "Диалог" })}
        >
          {empty ? (
            <p className={styles.chatEmpty}>
              Это чат с астропомощником. Спросите про день, карту или совместимость.
              {premium ? " " : " Один вопрос стоит "}
              {premium ? null : <StarPrice amount={QUESTION_STARS} />}
              {premium ? null : " звёзд. "}
              Ответ развлекательный и не обещает точное событие.
            </p>
          ) : null}
          {messages.map((message) => (
            <ChatBubble
              key={message.id}
              role={message.role === "user" ? "user" : "assistant"}
              text={message.content}
              time={clock(message.created_at)}
            />
          ))}
          {showUser && live !== null ? <ChatBubble role="user" text={live.text} time={clock(live.at)} /> : null}
          {showAssistant && live !== null ? (
            <ChatBubble role="assistant" text={answer} time="" pending={ask.isPending} announce />
          ) : null}
          <div ref={tail} />
        </div>
        <div className={styles.chatDock}>
          {premium && remaining !== undefined && remaining !== null ? (
            <Chip>Осталось {remaining} вопросов</Chip>
          ) : null}
          {!premium ? (
            <Chip>
              <StarPrice amount={QUESTION_STARS} /> звёзд за вопрос
            </Chip>
          ) : null}
          <ChatInput
            value={draft}
            pending={ask.isPending || history.isLoading}
            locked={short}
            placeholder={short ? "Недостаточно звёзд" : "Написать сообщение…"}
            onChange={setDraft}
            onSubmit={() => {
              const text = draft.trim();
              if (text === "" || ask.isPending || history.isLoading || short) {
                return;
              }
              const outgoing = {
                text,
                at: new Date().toISOString(),
                knownIds: messages.map((message) => message.id),
              };
              setDraft("");
              setLive(outgoing);
              ask.mutate(outgoing);
            }}
          />
        </div>
      </div>
      {topUp ? <TopUpDialog balance={null} onClose={() => setTopUp(false)} /> : null}
    </Screen>
  );
}

function alreadyStored(
  messages: AssistantMessage[],
  known: Set<string>,
  role: "user" | "assistant",
  content: string,
): boolean {
  if (content === "") {
    return false;
  }
  return messages.some((message) => {
    const sameRole = role === "user" ? message.role === "user" : message.role !== "user";
    return sameRole && message.content === content && !known.has(message.id);
  });
}

function assistantLine(reply: AssistantReply | undefined, failed: boolean): string {
  if (reply?.status === "stars") {
    return "На балансе не хватает звёзд.";
  }
  if (reply?.status === "premium") {
    return "Этот шаг доступен с Premium.";
  }
  if (reply?.status === "limit") {
    return reply.reply != null && reply.reply !== "" ? reply.reply : "Вопросы этого периода закончились.";
  }
  if (
    (reply?.status === "ready" || reply?.status === "off_topic" || reply?.status === "injection") &&
    reply.reply != null &&
    reply.reply !== ""
  ) {
    return reply.reply;
  }
  if (failed || reply !== undefined) {
    return STAR_SILENCE;
  }
  return "";
}

function clock(iso: string): string {
  const moment = new Date(iso);
  if (Number.isNaN(moment.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("ru", { hour: "2-digit", minute: "2-digit" }).format(moment);
}
