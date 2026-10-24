import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  askAssistant,
  getAssistantMessages,
  readingKey,
  type AssistantHistory,
} from "../api/client";
import { queryKeys } from "../api/keys";
import { ChatBubble } from "../shared/ui/ChatBubble/ChatBubble";
import { ChatInput } from "../shared/ui/ChatInput/ChatInput";
import { Chip } from "../shared/ui/Chip/Chip";
import { Screen } from "../shared/ui/Screen/Screen";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

const STORED = new Set(["ready", "off_topic", "injection"]);

export function ChatScreen() {
  const client = useQueryClient();
  const [draft, setDraft] = useState("");
  const history = useQuery({ queryKey: queryKeys.assistant, queryFn: () => getAssistantMessages() });
  const ask = useMutation({
    mutationFn: (text: string) => askAssistant(text, readingKey()),
    onSuccess: async (result, question) => {
      const answer = result.reply;
      if (!STORED.has(result.status) || answer == null) {
        return;
      }
      setDraft("");
      const stamp = new Date().toISOString();
      client.setQueryData<AssistantHistory>(queryKeys.assistant, (current) => ({
        messages: [
          ...(current?.messages ?? []),
          { id: `local-user-${stamp}`, role: "user", content: question, created_at: stamp },
          { id: `local-assistant-${stamp}`, role: "assistant", content: answer, created_at: stamp },
        ],
        remaining: result.remaining,
      }));
      await client.invalidateQueries({ queryKey: queryKeys.assistant, exact: true });
    },
  });
  const messages = history.data?.messages ?? [];
  const reply = ask.data?.reply;
  const echoed =
    reply != null && messages.some((message) => message.role !== "user" && message.content === reply);
  const remaining = ask.data?.remaining ?? history.data?.remaining;
  return (
    <Screen tab="chat">
      <div className={styles.fill}>
        <TopBar title="Астропомощник" back />
        <div className={styles.stack}>
          {messages.map((message) => (
            <ChatBubble
              key={message.id}
              role={message.role === "user" ? "user" : "assistant"}
              text={message.content}
              time={clock(message.created_at)}
            />
          ))}
          {reply != null && reply !== "" && !echoed ? (
            <ChatBubble role="assistant" text={reply} time="" />
          ) : null}
        </div>
        {remaining !== undefined && remaining !== null ? <Chip>Осталось {remaining} вопросов</Chip> : null}
        <div className={styles.dock}>
          <ChatInput
            value={draft}
            pending={ask.isPending}
            onChange={setDraft}
            onSubmit={() => {
              ask.mutate(draft);
            }}
          />
        </div>
      </div>
    </Screen>
  );
}

function clock(iso: string): string {
  const moment = new Date(iso);
  if (Number.isNaN(moment.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("ru", { hour: "2-digit", minute: "2-digit" }).format(moment);
}
