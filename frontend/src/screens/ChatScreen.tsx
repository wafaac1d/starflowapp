import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { askAssistant, getAssistantMessages, readingKey } from "../api/client";
import { getAssistantQuota } from "../api/fixtures";
import { queryKeys } from "../api/keys";
import { ChatBubble } from "../shared/ui/ChatBubble/ChatBubble";
import { ChatInput } from "../shared/ui/ChatInput/ChatInput";
import { Chip } from "../shared/ui/Chip/Chip";
import { Screen } from "../shared/ui/Screen/Screen";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

export function ChatScreen() {
  const client = useQueryClient();
  const [draft, setDraft] = useState("");
  const history = useQuery({ queryKey: queryKeys.assistant, queryFn: () => getAssistantMessages() });
  const quota = useQuery({ queryKey: queryKeys.assistantQuota, queryFn: getAssistantQuota });
  const ask = useMutation({
    mutationFn: (text: string) => askAssistant(text, readingKey()),
    onSuccess: async (result) => {
      if (result.status === "ready" || result.status === "off_topic" || result.status === "injection") {
        setDraft("");
        await client.invalidateQueries({ queryKey: queryKeys.assistant });
      }
    },
  });
  const remaining = ask.data?.remaining ?? quota.data?.remaining;
  return (
    <Screen tab="chat">
      <div className={styles.fill}>
        <TopBar title="Астропомощник" back />
        <div className={styles.stack}>
          {(history.data ?? []).map((message) => (
            <ChatBubble
              key={message.id}
              role={message.role === "user" ? "user" : "assistant"}
              text={message.content}
              time={clock(message.created_at)}
            />
          ))}
          {ask.data?.reply ? <ChatBubble role="assistant" text={ask.data.reply} time="" /> : null}
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
