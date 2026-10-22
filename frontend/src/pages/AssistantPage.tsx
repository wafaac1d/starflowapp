import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  askAssistant,
  getAssistantMessages,
  readingKey,
  type AssistantMessage,
} from "../api/client";
import { BackHome, Button } from "../components/ui/controls";
import { text } from "../resources";

type FetchProps = {
  fetchImpl?: typeof fetch;
};

export function AssistantPage({ fetchImpl = fetch }: FetchProps) {
  const client = useQueryClient();
  const [draft, setDraft] = useState("");
  const [older, setOlder] = useState<AssistantMessage[]>([]);
  const history = useQuery({
    queryKey: ["assistant"],
    queryFn: () => getAssistantMessages(fetchImpl),
    retry: false,
  });
  const ask = useMutation({
    mutationFn: (value: string) => askAssistant(value, readingKey(), fetchImpl),
    onSuccess: async () => {
      setDraft("");
      await client.invalidateQueries({ queryKey: ["assistant"] });
    },
  });
  const messages = [...older, ...(history.data ?? [])];
  const earliest = messages[0]?.created_at;
  const pending = ask.isPending;
  const tooLong = draft.length > 500;
  const reply = ask.data;

  return (
    <main className="shell chat-shell">
      <h1>{text("ui.assistant.title")}</h1>
      <p className="lead">{text("ui.assistant.disclaimer")}</p>
      {history.isPending ? <p>{text("ui.common.loading")}</p> : null}
      {history.isError ? <p role="alert">{text("ui.common.error")}</p> : null}
      {history.data !== undefined && messages.length === 0 ? (
        <p>{text("ui.assistant.empty")}</p>
      ) : null}
      {earliest !== undefined ? (
        <Button
          tone="outline"
          label={text("ui.assistant.earlier")}
          onClick={() => {
            void getAssistantMessages(fetchImpl, earliest).then((page) => {
              setOlder((current) => [...page, ...current]);
            });
          }}
        />
      ) : null}
      <div className="chat-log">
        {messages.map((message) => (
          <p key={message.id} className={message.role === "user" ? "chat-user" : "chat-reply"}>
            {message.content}
          </p>
        ))}
      </div>
      {reply?.reply && !messages.some((message) => message.content === reply.reply) ? (
        <p className="chat-reply">{reply.reply}</p>
      ) : null}
      {reply?.remaining !== null && reply?.remaining !== undefined ? (
        <p>
          {text("ui.assistant.remaining")}: {reply.remaining}
        </p>
      ) : null}
      {ask.isError ? <p role="alert">{text("ui.common.error")}</p> : null}
      {reply?.status === "premium" || reply?.status === "limit" ? (
        <p role="alert">{reply.reply || text("ui.assistant.quota")}</p>
      ) : null}
      <form
        className="chat-dock"
        onSubmit={(event) => {
          event.preventDefault();
          if (draft.trim() === "" || tooLong || pending) {
            return;
          }
          ask.mutate(draft);
        }}
      >
        <label htmlFor="assistant-question">{text("ui.assistant.title")}</label>
        <textarea
          id="assistant-question"
          className="chat-input"
          value={draft}
          maxLength={500}
          onChange={(event) => {
            setDraft(event.target.value);
          }}
        />
        <button className="button" type="submit" disabled={draft.trim() === "" || tooLong || pending}>
          {text("ui.assistant.send")}
        </button>
      </form>
      <BackHome />
    </main>
  );
}
