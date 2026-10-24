import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useNavigate } from "react-router";

import {
  askAssistant,
  getAssistantMessages,
  readingKey,
  type AssistantMessage,
  type AssistantReply,
} from "../api/client";
import { Button } from "../components/ui/controls";
import { ChatComposer, ChatMessage, PageHeader } from "../components/ui/editorial";
import { text } from "../resources";

type FetchProps = {
  fetchImpl?: typeof fetch;
};

const STORED = new Set(["ready", "off_topic", "injection"]);

export function AssistantPage({ fetchImpl = fetch }: FetchProps) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [draft, setDraft] = useState("");
  const [older, setOlder] = useState<AssistantMessage[]>([]);
  const key = useRef(readingKey());
  const log = useRef<HTMLDivElement>(null);
  const history = useQuery({
    queryKey: ["assistant"],
    queryFn: () => getAssistantMessages(fetchImpl),
    retry: false,
  });
  const ask = useMutation({
    mutationFn: (value: string) => askAssistant(value, key.current, fetchImpl),
    onSuccess: async (result) => {
      if (STORED.has(result.status)) {
        setDraft("");
        key.current = readingKey();
        await client.invalidateQueries({ queryKey: ["assistant"], exact: true });
        window.setTimeout(() => {
          log.current?.lastElementChild?.scrollIntoView({ block: "nearest" });
        }, 0);
      }
    },
  });
  const messages = [...older, ...(history.data?.messages ?? [])];
  const earliest = messages[0]?.created_at;
  const reply = ask.data;

  return (
    <main className="shell page chat-shell">
      <PageHeader title={text("ui.assistant.title")} backTo="/" />
      <p className="lead">{text("ui.assistant.disclaimer")}</p>
      {reply?.remaining !== null && reply?.remaining !== undefined ? (
        <p className="profile-meta">
          {text("ui.assistant.remaining")}: {reply.remaining}
        </p>
      ) : null}
      {history.isPending ? <p>{text("ui.common.loading")}</p> : null}
      {history.isError ? <p role="alert">{text("ui.common.error")}</p> : null}
      {history.data !== undefined && messages.length === 0 && reply === undefined ? (
        <p>{text("ui.assistant.empty")}</p>
      ) : null}
      {earliest !== undefined ? (
        <Button
          tone="outline"
          label={text("ui.assistant.earlier")}
          onClick={() => {
            void getAssistantMessages(fetchImpl, earliest).then((page) => {
              setOlder((current) => [...page.messages, ...current]);
            });
          }}
        />
      ) : null}
      <div className="chat-log" ref={log}>
        {messages.map((message, index) => (
          <MessageBlock key={message.id} message={message} previous={messages[index - 1]} />
        ))}
      </div>
      {reply?.reply && !messages.some((message) => message.content === reply.reply) ? (
        <ChatMessage role="assistant" content={reply.reply} />
      ) : null}
      <ReplyState reply={reply} failed={ask.isError} onPremium={() => void navigate("/premium")} />
      <ChatComposer
        value={draft}
        pending={ask.isPending}
        onChange={setDraft}
        onSubmit={() => {
          ask.mutate(draft);
        }}
      />
    </main>
  );
}

function MessageBlock({
  message,
  previous,
}: {
  message: AssistantMessage;
  previous: AssistantMessage | undefined;
}) {
  const day = dayLabel(message.created_at);
  const showDay = day !== "" && day !== dayLabel(previous?.created_at);
  return (
    <>
      {showDay ? <p className="chat-date">{day}</p> : null}
      <ChatMessage role={message.role} content={message.content} />
    </>
  );
}

function ReplyState({
  reply,
  failed,
  onPremium,
}: {
  reply: AssistantReply | undefined;
  failed: boolean;
  onPremium: () => void;
}) {
  if (reply?.status === "premium") {
    return (
      <>
        <p role="alert">{text("ui.paywall.title")}</p>
        <Button label={text("ui.premium.title")} onClick={onPremium} />
      </>
    );
  }
  if (reply?.status === "limit") {
    return <p role="alert">{reply.reply || text("ui.assistant.quota")}</p>;
  }
  if (reply?.status === "error" || failed) {
    return <p role="alert">{reply?.reply || text("ui.common.error")}</p>;
  }
  return null;
}

function dayLabel(value: string | undefined): string {
  if (value === undefined) {
    return "";
  }
  const moment = new Date(value);
  if (Number.isNaN(moment.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("ru", { day: "numeric", month: "long" }).format(moment);
}
