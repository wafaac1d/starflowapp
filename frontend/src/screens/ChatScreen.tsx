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
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

const STORED = new Set(["ready", "off_topic", "injection"]);

type Outgoing = {
  text: string;
  at: string;
  knownIds: string[];
};

export function ChatScreen({ premium }: { premium: boolean }) {
  const client = useQueryClient();
  const [draft, setDraft] = useState("");
  const [live, setLive] = useState<Outgoing | null>(null);
  const history = useQuery({ queryKey: queryKeys.assistant, queryFn: () => getAssistantMessages() });
  const ask = useMutation({
    mutationFn: (outgoing: Outgoing) => askAssistant(outgoing.text, readingKey()),
    onSuccess: (result) => {
      if (!STORED.has(result.status) || result.reply == null || result.reply === "") {
        return;
      }
      void client.invalidateQueries({ queryKey: queryKeys.assistant, exact: true });
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
  const tail = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = tail.current;
    if (node !== null && typeof node.scrollIntoView === "function") {
      node.scrollIntoView({ block: "nearest" });
    }
  }, [question, answer, ask.isPending]);
  return (
    <Screen tab="chat">
      <div className={styles.fill}>
        <TopBar title="Астропомощник" back />
        <div className={empty ? styles.chatEmptyStage : styles.stack}>
          {empty ? (
            <p className={styles.chatEmpty}>
              Это чат с астропомощником. Спросите про день, карту или совместимость.
              {premium ? " " : " Писать и отправлять сообщения можно с Premium. "}
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
        {remaining !== undefined && remaining !== null ? <Chip>Осталось {remaining} вопросов</Chip> : null}
        <div className={styles.dock}>
          {!premium && history.isSuccess && !empty ? (
            <p className={styles.chatLock}>Писать и отправлять сообщения можно с Premium.</p>
          ) : null}
          <ChatInput
            value={draft}
            locked={!premium}
            pending={ask.isPending || history.isLoading}
            onChange={setDraft}
            onSubmit={() => {
              const text = draft.trim();
              if (!premium || text === "" || ask.isPending || history.isLoading) {
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
